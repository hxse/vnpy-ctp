// Linux 快照绑定。原生回调只保留每个活跃合约的一条待交付报价。
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "ctp/ThostFtdcMdApi.h"

#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <limits>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

constexpr size_t max_symbols = 64;
constexpr size_t max_controls = max_symbols * 4 + 16;

template <size_t N>
std::string field(const char (&value)[N]) {
    return std::string(value, strnlen(value, N));
}

template <size_t N>
void copy_field(char (&target)[N], const py::dict &fields, const char *name) {
    const auto value = py::cast<std::string>(fields[name]);
    if (value.size() >= N || value.find('\0') != std::string::npos) {
        throw std::invalid_argument("invalid CTP login field");
    }
    std::memcpy(target, value.c_str(), value.size() + 1);
}

struct Quote {
    std::string instrument;
    std::string exchange;
    std::string trading_day;
    std::string action_day;
    std::string update_time;
    int update_millis;
    double last_price;
};

struct Control {
    const char *kind;
    std::string instrument;
    int error_id;
};

class MdApi final : public CThostFtdcMdSpi {
public:
    ~MdApi() { exit(); }

    void create(const std::string &flow, bool production) {
        std::lock_guard lock(commands);
        if (api || closed) throw std::logic_error("market API already created or released");
        api = CThostFtdcMdApi::CreateFtdcMdApi(flow.c_str(), false, false, production);
        if (!api) throw std::runtime_error("cannot create CTP market API");
        api->RegisterSpi(this);
    }

    void register_front(std::string front) {
        std::lock_guard lock(commands);
        native().RegisterFront(front.data());
    }

    void init() {
        std::lock_guard lock(commands);
        native().Init();
        initialized = true;
    }

    int login(const py::dict &fields, int request_id) {
        CThostFtdcReqUserLoginField request{};
        copy_field(request.BrokerID, fields, "BrokerID");
        copy_field(request.UserID, fields, "UserID");
        copy_field(request.Password, fields, "Password");
        copy_field(request.UserProductInfo, fields, "UserProductInfo");
        std::lock_guard lock(commands);
        return native().ReqUserLogin(&request, request_id);
    }

    int subscribe(std::vector<std::string> instruments) {
        validate(instruments);
        std::lock_guard lock(commands);
        auto &client = native();
        {
            std::lock_guard state_lock(state);
            if (slots.size() + instruments.size() > max_symbols) return -2;
            for (const auto &name : instruments) {
                if (slots.count(name)) throw std::invalid_argument("market contract already active");
            }
            for (const auto &name : instruments) slots.try_emplace(name);
        }
        auto values = pointers(instruments);
        const int result = client.SubscribeMarketData(values.data(), static_cast<int>(values.size()));
        if (result) {
            std::lock_guard state_lock(state);
            for (const auto &name : instruments) slots.erase(name);
        }
        return result;
    }

    int unsubscribe(std::vector<std::string> instruments) {
        validate(instruments);
        auto values = pointers(instruments);
        std::lock_guard lock(commands);
        return native().UnSubscribeMarketData(values.data(), static_cast<int>(values.size()));
    }

    py::list read_events(int timeout_ms) {
        if (timeout_ms < 0) throw std::invalid_argument("negative market wait");
        std::deque<Control> received;
        std::vector<Quote> quotes;
        {
            py::gil_scoped_release release;
            std::unique_lock lock(state);
            changed.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&] {
                return closed || !controls.empty() || have_quote;
            });
            received.swap(controls);
            for (auto &entry : slots) {
                if (entry.second) {
                    quotes.push_back(std::move(*entry.second));
                    entry.second.reset();
                }
            }
            have_quote = false;
        }
        py::list result;
        using namespace py::literals;
        for (const auto &event : received) {
            result.append(py::dict("kind"_a=event.kind, "instrument"_a=event.instrument, "error_id"_a=event.error_id));
        }
        for (const auto &quote : quotes) {
            result.append(py::dict("kind"_a="quote", "instrument"_a=quote.instrument, "exchange"_a=quote.exchange,
                                   "trading_day"_a=quote.trading_day, "action_day"_a=quote.action_day,
                                   "update_time"_a=quote.update_time, "update_millis"_a=quote.update_millis,
                                   "last_price"_a=quote.last_price));
        }
        return result;
    }

    void exit() {
        std::lock_guard lock(commands);
        {
            std::lock_guard state_lock(state);
            closed = true;
            slots.clear();
            controls.clear();
            changed.notify_all();
        }
        if (auto *client = std::exchange(api, nullptr)) {
            client->RegisterSpi(nullptr);
            // 厂商 6.7.13 必须先启动内部线程才能安全释放。
            if (!initialized) client->Init();
            client->Release();
        }
    }

    void OnFrontConnected() override { push("connected", {}, 0); }

    void OnFrontDisconnected(int reason) override {
        std::lock_guard lock(state);
        slots.clear();
        push_locked("disconnected", {}, reason);
    }

    void OnRspUserLogin(CThostFtdcRspUserLoginField *data, CThostFtdcRspInfoField *info, int, bool last) override {
        if (last) push("login", {}, data || error_id(info) ? error_id(info) : -1);
    }

    void OnRspSubMarketData(CThostFtdcSpecificInstrumentField *data, CThostFtdcRspInfoField *info, int, bool) override {
        if (data) push("subscribed", field(data->InstrumentID), error_id(info));
        else if (error_id(info)) push("error", {}, error_id(info));
    }

    void OnRspUnSubMarketData(CThostFtdcSpecificInstrumentField *data, CThostFtdcRspInfoField *info, int, bool) override {
        if (!data) {
            if (error_id(info)) push("error", {}, error_id(info));
            return;
        }
        auto name = field(data->InstrumentID);
        std::lock_guard lock(state);
        if (!error_id(info)) slots.erase(name);
        push_locked("unsubscribed", std::move(name), error_id(info));
    }

    void OnRspError(CThostFtdcRspInfoField *info, int, bool) override {
        if (error_id(info)) push("error", {}, error_id(info));
    }

    void OnRtnDepthMarketData(CThostFtdcDepthMarketDataField *data) override {
        if (!data || !std::isfinite(data->LastPrice)
            || std::abs(data->LastPrice) == std::numeric_limits<double>::max()) return;
        auto name = field(data->InstrumentID);
        std::lock_guard lock(state);
        const auto position = slots.find(name);
        if (position == slots.end() || position->second || overflow) return;
        position->second = Quote{std::move(name), field(data->ExchangeID), field(data->TradingDay),
                                 field(data->ActionDay), field(data->UpdateTime), data->UpdateMillisec, data->LastPrice};
        have_quote = true;
        changed.notify_one();
    }

private:
    static int error_id(CThostFtdcRspInfoField *info) { return info ? info->ErrorID : 0; }

    void push(const char *kind, std::string instrument, int code) {
        std::lock_guard lock(state);
        push_locked(kind, std::move(instrument), code);
    }

    void push_locked(const char *kind, std::string instrument, int code) {
        if (closed || overflow) return;
        if (controls.size() == max_controls) {
            // 控制事实无法完整保留时通知应用废弃本代。
            overflow = true;
            slots.clear();
            controls.clear();
            controls.push_back({"overflow", {}, 0});
        } else {
            controls.push_back({kind, std::move(instrument), code});
        }
        changed.notify_one();
    }

    CThostFtdcMdApi &native() {
        if (!api) throw std::logic_error("market API is closed");
        return *api;
    }

    static void validate(const std::vector<std::string> &names) {
        if (names.empty() || names.size() > max_symbols) throw std::invalid_argument("invalid CTP market batch");
        std::unordered_set<std::string> unique;
        for (const auto &name : names) {
            if (name.empty() || name.size() >= sizeof(TThostFtdcInstrumentIDType)
                || name.find('\0') != std::string::npos || !unique.insert(name).second) {
                throw std::invalid_argument("invalid CTP market contract");
            }
        }
    }

    static std::vector<char *> pointers(std::vector<std::string> &names) {
        std::vector<char *> result;
        result.reserve(names.size());
        for (auto &name : names) result.push_back(name.data());
        return result;
    }

    std::mutex commands;
    std::mutex state;
    std::condition_variable changed;
    CThostFtdcMdApi *api = nullptr;
    std::deque<Control> controls;
    std::unordered_map<std::string, std::optional<Quote>> slots;
    bool initialized = false;
    bool closed = false;
    bool overflow = false;
    bool have_quote = false;
};

} // namespace

PYBIND11_MODULE(vnctpmd, module) {
    py::class_<MdApi>(module, "MdApi")
        .def(py::init<>())
        .def_static("getApiVersion", &CThostFtdcMdApi::GetApiVersion)
        .def("createFtdcMdApi", &MdApi::create)
        .def("registerFront", &MdApi::register_front)
        .def("init", &MdApi::init)
        .def("reqUserLogin", &MdApi::login)
        .def("subscribeMarketData", &MdApi::subscribe)
        .def("unSubscribeMarketData", &MdApi::unsubscribe)
        .def("readEvents", &MdApi::read_events)
        .def("exit", &MdApi::exit, py::call_guard<py::gil_scoped_release>());
}

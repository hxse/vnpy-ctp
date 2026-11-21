#include "ctp/ThostFtdcMdApi.h"
#include "lifecycle.hpp"

using vnctp_go::call;
using vnctp_go::event;
using vnctp_go::notice;

struct vnctp_go_md final : CThostFtdcMdSpi {
    explicit vnctp_go_md(uint32_t capacity) : owner(capacity, VNCTP_GO_MAX_CONTRACTS) {}

    void OnFrontConnected() override { owner.inbox.push(notice(VNCTP_GO_FRONT_CONNECTED)); }
    void OnFrontDisconnected(int reason) override {
        owner.inbox.push(notice(VNCTP_GO_FRONT_DISCONNECTED, reason));
    }
    void OnRspError(CThostFtdcRspInfoField *error, int id, bool last) override {
        owner.inbox.push(event<int>(VNCTP_GO_RSP_ERROR, nullptr, error, id, last));
    }
    void OnRspUserLogin(CThostFtdcRspUserLoginField *row, CThostFtdcRspInfoField *error, int id, bool last) override {
        owner.inbox.push(event(VNCTP_GO_RSP_USER_LOGIN, row, error, id, last));
    }
    void OnRspSubMarketData(CThostFtdcSpecificInstrumentField *row, CThostFtdcRspInfoField *error, int id, bool last) override {
        owner.inbox.push(event(VNCTP_GO_RSP_SUBSCRIBE, row, error, id, last));
    }
    void OnRspUnSubMarketData(CThostFtdcSpecificInstrumentField *row, CThostFtdcRspInfoField *error, int id, bool last) override {
        owner.inbox.push(event(VNCTP_GO_RSP_UNSUBSCRIBE, row, error, id, last));
    }
    void OnRtnDepthMarketData(CThostFtdcDepthMarketDataField *row) override {
        owner.inbox.quote(row);
    }
    vnctp_go::Handle<CThostFtdcMdApi> owner;
};

namespace {

int change_subscription(vnctp_go_md *handle, const vnctp_go_symbol *symbols, uint32_t count, bool add) {
    if (!symbols || count == 0 || count > VNCTP_GO_MAX_CONTRACTS) return VNCTP_GO_INVALID;
    std::array<vnctp_go_symbol, VNCTP_GO_MAX_CONTRACTS> local{};
    std::array<char *, VNCTP_GO_MAX_CONTRACTS> names{};
    for (uint32_t i = 0; i < count; ++i) {
        if (!symbols[i].instrument[0] || !std::memchr(symbols[i].instrument, 0, sizeof(symbols[i].instrument))) {
            return VNCTP_GO_INVALID;
        }
        for (uint32_t earlier = 0; earlier < i; ++earlier) {
            if (!std::strcmp(symbols[earlier].instrument, symbols[i].instrument)) return VNCTP_GO_INVALID;
        }
        local[i] = symbols[i];
        names[i] = local[i].instrument;
    }

    return call(handle, [&](auto &value) {
        return value.owner.send([&](auto &api) {
            if (!add) return api.UnSubscribeMarketData(names.data(), static_cast<int>(count));
            if (const int reserved = value.owner.inbox.reserve(local.data(), count)) return reserved;
            const int result = api.SubscribeMarketData(names.data(), static_cast<int>(count));
            if (result) value.owner.inbox.rollback(local.data(), count);
            return result;
        });
    });
}

} // namespace

const char *vnctp_go_md_sdk_version(void) {
    return CThostFtdcMdApi::GetApiVersion();
}

vnctp_go_md *vnctp_go_md_create(const char *flow, int production, uint32_t capacity) {
    return vnctp_go::create<vnctp_go_md>(flow, production, capacity, [](const char *path, bool active) {
        return CThostFtdcMdApi::CreateFtdcMdApi(path, false, false, active);
    });
}

int vnctp_go_md_start(vnctp_go_md *handle, const char *front) {
    return call(handle, [&](auto &value) {
        return value.owner.start(&value, front, [](auto &) {});
    });
}

int vnctp_go_md_login(vnctp_go_md *handle, const CThostFtdcReqUserLoginField *data, int32_t id) {
    if (!data || id <= 0) return VNCTP_GO_INVALID;
    auto input = *data;
    return call(handle, [&](auto &value) {
        return value.owner.send([&](auto &api) { return api.ReqUserLogin(&input, id); });
    });
}

int vnctp_go_md_subscribe(vnctp_go_md *handle, const vnctp_go_symbol *symbols, uint32_t count) {
    return change_subscription(handle, symbols, count, true);
}

int vnctp_go_md_unsubscribe(vnctp_go_md *handle, const vnctp_go_symbol *symbols, uint32_t count) {
    return change_subscription(handle, symbols, count, false);
}

int vnctp_go_md_poll(vnctp_go_md *handle, vnctp_go_event *events, uint32_t capacity, uint32_t timeout_ms) {
    return call(handle, [&](auto &value) { return value.owner.inbox.poll(events, capacity, timeout_ms); });
}

int vnctp_go_md_stop(vnctp_go_md *handle) {
    return call(handle, [](auto &value) { return value.owner.stop(); });
}

int vnctp_go_md_destroy(vnctp_go_md *handle) {
    return vnctp_go::destroy(handle);
}

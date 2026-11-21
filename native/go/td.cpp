#include "ctp/ThostFtdcTraderApi.h"
#include "lifecycle.hpp"

using vnctp_go::call;
using vnctp_go::event;
using vnctp_go::notice;

struct vnctp_go_td final : CThostFtdcTraderSpi {
    explicit vnctp_go_td(uint32_t capacity) : owner(capacity) {}

    void OnFrontConnected() override { owner.inbox.push(notice(VNCTP_GO_FRONT_CONNECTED)); }
    void OnFrontDisconnected(int reason) override {
        owner.inbox.push(notice(VNCTP_GO_FRONT_DISCONNECTED, reason));
    }
    void OnRspError(CThostFtdcRspInfoField *error, int id, bool last) override {
        owner.inbox.push(event<int>(VNCTP_GO_RSP_ERROR, nullptr, error, id, last));
    }

#define REPLY(callback, record, kind) \
    void callback(record *row, CThostFtdcRspInfoField *error, int id, bool last) override { \
        owner.inbox.push(event(kind, row, error, id, last)); \
    }
    REPLY(OnRspAuthenticate, CThostFtdcRspAuthenticateField, VNCTP_GO_RSP_AUTHENTICATE)
    REPLY(OnRspUserLogin, CThostFtdcRspUserLoginField, VNCTP_GO_RSP_USER_LOGIN)
    REPLY(OnRspSettlementInfoConfirm, CThostFtdcSettlementInfoConfirmField, VNCTP_GO_RSP_SETTLEMENT_CONFIRM)
    REPLY(OnRspOrderInsert, CThostFtdcInputOrderField, VNCTP_GO_RSP_ORDER_INSERT)
    REPLY(OnRspOrderAction, CThostFtdcInputOrderActionField, VNCTP_GO_RSP_ORDER_ACTION)
    REPLY(OnRspQryOrder, CThostFtdcOrderField, VNCTP_GO_RSP_QRY_ORDER)
    REPLY(OnRspQryTrade, CThostFtdcTradeField, VNCTP_GO_RSP_QRY_TRADE)
    REPLY(OnRspQryInvestorPosition, CThostFtdcInvestorPositionField, VNCTP_GO_RSP_QRY_POSITION)
    REPLY(OnRspQryTradingAccount, CThostFtdcTradingAccountField, VNCTP_GO_RSP_QRY_ACCOUNT)
    REPLY(OnRspQryInstrument, CThostFtdcInstrumentField, VNCTP_GO_RSP_QRY_INSTRUMENT)
#undef REPLY

    void OnRtnOrder(CThostFtdcOrderField *row) override {
        owner.inbox.push(event(VNCTP_GO_RTN_ORDER, row));
    }
    void OnRtnTrade(CThostFtdcTradeField *row) override {
        owner.inbox.push(event(VNCTP_GO_RTN_TRADE, row));
    }
    void OnRtnInstrumentStatus(CThostFtdcInstrumentStatusField *row) override {
        owner.inbox.push(event(VNCTP_GO_RTN_INSTRUMENT_STATUS, row));
    }
    void OnErrRtnOrderInsert(CThostFtdcInputOrderField *row, CThostFtdcRspInfoField *error) override {
        owner.inbox.push(event(VNCTP_GO_ERR_RTN_ORDER_INSERT, row, error));
    }
    void OnErrRtnOrderAction(CThostFtdcOrderActionField *row, CThostFtdcRspInfoField *error) override {
        owner.inbox.push(event(VNCTP_GO_ERR_RTN_ORDER_ACTION, row, error));
    }
    vnctp_go::Handle<CThostFtdcTraderApi> owner;
};

namespace {

template <typename Row, int (CThostFtdcTraderApi::*Send)(Row *, int)>
int request(CThostFtdcTraderApi &api, const void *data, uint32_t size, int32_t id) {
    if (size != sizeof(Row)) return VNCTP_GO_INVALID;
    Row input{};
    std::memcpy(&input, data, size);
    return (api.*Send)(&input, id);
}

} // namespace

uint32_t vnctp_go_abi_version(void) { return VNCTP_GO_ABI_VERSION; }

const char *vnctp_go_td_sdk_version(void) {
    return CThostFtdcTraderApi::GetApiVersion();
}

vnctp_go_td *vnctp_go_td_create(const char *flow, int production, uint32_t capacity) {
    return vnctp_go::create<vnctp_go_td>(flow, production, capacity, CThostFtdcTraderApi::CreateFtdcTraderApi);
}

int vnctp_go_td_start(vnctp_go_td *handle, const char *front, int private_topic, int public_topic) {
    if (private_topic < 0 || private_topic > 2 || public_topic < 0 || public_topic > 2) {
        return VNCTP_GO_INVALID;
    }
    return call(handle, [&](auto &value) {
        return value.owner.start(&value, front, [&](auto &api) {
            api.SubscribePrivateTopic(static_cast<THOST_TE_RESUME_TYPE>(private_topic));
            api.SubscribePublicTopic(static_cast<THOST_TE_RESUME_TYPE>(public_topic));
        });
    });
}

int vnctp_go_td_request(vnctp_go_td *handle, uint32_t kind, const void *data, uint32_t size, int32_t id) {
    if (!data || id <= 0) return VNCTP_GO_INVALID;
    return call(handle, [&](auto &value) {
        return value.owner.send([&](auto &api) -> int {
            switch (kind) {
#define SEND(kind, row, method) \
                case kind: return request<row, &CThostFtdcTraderApi::method>(api, data, size, id);
                SEND(VNCTP_GO_REQ_AUTHENTICATE, CThostFtdcReqAuthenticateField, ReqAuthenticate)
                SEND(VNCTP_GO_REQ_USER_LOGIN, CThostFtdcReqUserLoginField, ReqUserLogin)
                SEND(VNCTP_GO_REQ_SETTLEMENT_CONFIRM, CThostFtdcSettlementInfoConfirmField, ReqSettlementInfoConfirm)
                SEND(VNCTP_GO_REQ_ORDER_INSERT, CThostFtdcInputOrderField, ReqOrderInsert)
                SEND(VNCTP_GO_REQ_ORDER_ACTION, CThostFtdcInputOrderActionField, ReqOrderAction)
                SEND(VNCTP_GO_REQ_QRY_ORDER, CThostFtdcQryOrderField, ReqQryOrder)
                SEND(VNCTP_GO_REQ_QRY_TRADE, CThostFtdcQryTradeField, ReqQryTrade)
                SEND(VNCTP_GO_REQ_QRY_POSITION, CThostFtdcQryInvestorPositionField, ReqQryInvestorPosition)
                SEND(VNCTP_GO_REQ_QRY_ACCOUNT, CThostFtdcQryTradingAccountField, ReqQryTradingAccount)
                SEND(VNCTP_GO_REQ_QRY_INSTRUMENT, CThostFtdcQryInstrumentField, ReqQryInstrument)
#undef SEND
                default: return VNCTP_GO_INVALID;
            }
        });
    });
}

int vnctp_go_td_front_info(vnctp_go_td *handle, CThostFtdcFrontInfoField *output) {
    if (!output) return VNCTP_GO_INVALID;
    *output = {};
    return call(handle, [&](auto &value) {
        return value.owner.send([&](auto &api) { api.GetFrontInfo(output); return 0; });
    });
}

int vnctp_go_td_trading_day(vnctp_go_td *handle, TThostFtdcDateType output) {
    if (!output) return VNCTP_GO_INVALID;
    std::memset(output, 0, sizeof(TThostFtdcDateType));
    return call(handle, [&](auto &value) {
        return value.owner.send([&](auto &api) {
            const auto *day = api.GetTradingDay();
            if (day) std::memcpy(output, day, strnlen(day, sizeof(TThostFtdcDateType) - 1));
            return 0;
        });
    });
}

int vnctp_go_td_poll(vnctp_go_td *handle, vnctp_go_event *events, uint32_t capacity, uint32_t timeout_ms) {
    return call(handle, [&](auto &value) { return value.owner.inbox.poll(events, capacity, timeout_ms); });
}

int vnctp_go_td_stop(vnctp_go_td *handle) {
    return call(handle, [](auto &value) { return value.owner.stop(); });
}

int vnctp_go_td_destroy(vnctp_go_td *handle) {
    return vnctp_go::destroy(handle);
}

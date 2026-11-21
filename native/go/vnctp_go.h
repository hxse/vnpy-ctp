#ifndef VNCTP_GO_H
#define VNCTP_GO_H

#include <stdint.h>
#include "ctp/ThostFtdcUserApiStruct.h"

#ifdef __cplusplus
extern "C" {
#endif

#define VNCTP_GO_ABI_VERSION 1
#define VNCTP_GO_MAX_CONTRACTS 64
#define VNCTP_GO_MAX_QUEUE 8192
#define VNCTP_GO_EXPORT __attribute__((visibility("default")))

enum vnctp_go_result {
    VNCTP_GO_INVALID = -20001,
    VNCTP_GO_CLOSED = -20002,
    VNCTP_GO_OVERFLOW = -20003,
    VNCTP_GO_NATIVE_FAILURE = -20004,
    VNCTP_GO_BAD_STATE = -20005,
};

enum vnctp_go_request {
    VNCTP_GO_REQ_AUTHENTICATE = 1,
    VNCTP_GO_REQ_USER_LOGIN = 2,
    VNCTP_GO_REQ_SETTLEMENT_CONFIRM = 3,
    VNCTP_GO_REQ_ORDER_INSERT = 4,
    VNCTP_GO_REQ_ORDER_ACTION = 5,
    VNCTP_GO_REQ_QRY_ORDER = 6,
    VNCTP_GO_REQ_QRY_TRADE = 7,
    VNCTP_GO_REQ_QRY_POSITION = 8,
    VNCTP_GO_REQ_QRY_ACCOUNT = 9,
    VNCTP_GO_REQ_QRY_INSTRUMENT = 10,
};

enum vnctp_go_event_kind {
    VNCTP_GO_FRONT_CONNECTED = 1,
    VNCTP_GO_FRONT_DISCONNECTED = 2,
    VNCTP_GO_RSP_ERROR = 3,
    VNCTP_GO_RSP_AUTHENTICATE = 4,
    VNCTP_GO_RSP_USER_LOGIN = 5,
    VNCTP_GO_RSP_SETTLEMENT_CONFIRM = 6,
    VNCTP_GO_RSP_ORDER_INSERT = 7,
    VNCTP_GO_RSP_ORDER_ACTION = 8,
    VNCTP_GO_RSP_QRY_ORDER = 9,
    VNCTP_GO_RSP_QRY_TRADE = 10,
    VNCTP_GO_RSP_QRY_POSITION = 11,
    VNCTP_GO_RSP_QRY_ACCOUNT = 12,
    VNCTP_GO_RSP_QRY_INSTRUMENT = 13,
    VNCTP_GO_RTN_ORDER = 14,
    VNCTP_GO_RTN_TRADE = 15,
    VNCTP_GO_RTN_INSTRUMENT_STATUS = 16,
    VNCTP_GO_ERR_RTN_ORDER_INSERT = 17,
    VNCTP_GO_ERR_RTN_ORDER_ACTION = 18,
    VNCTP_GO_RSP_SUBSCRIBE = 19,
    VNCTP_GO_RSP_UNSUBSCRIBE = 20,
    VNCTP_GO_RTN_QUOTE = 21,
};

typedef union vnctp_go_payload {
    struct CThostFtdcRspAuthenticateField authenticate;
    struct CThostFtdcRspUserLoginField login;
    struct CThostFtdcSettlementInfoConfirmField settlement;
    struct CThostFtdcInputOrderField input_order;
    struct CThostFtdcInputOrderActionField input_action;
    struct CThostFtdcOrderActionField order_action;
    struct CThostFtdcOrderField order;
    struct CThostFtdcTradeField trade;
    struct CThostFtdcInvestorPositionField position;
    struct CThostFtdcTradingAccountField account;
    struct CThostFtdcInstrumentField instrument;
    struct CThostFtdcInstrumentStatusField instrument_status;
    struct CThostFtdcSpecificInstrumentField subscription;
    struct CThostFtdcDepthMarketDataField quote;
} vnctp_go_payload;

typedef struct vnctp_go_event {
    uint32_t kind;
    int32_t request_id;
    int32_t reason;
    uint32_t data_size;
    uint32_t is_last;
    uint32_t has_error;
    struct CThostFtdcRspInfoField error;
    vnctp_go_payload data;
} vnctp_go_event;

typedef struct vnctp_go_symbol {
    TThostFtdcInstrumentIDType instrument;
} vnctp_go_symbol;

typedef struct vnctp_go_td vnctp_go_td;
typedef struct vnctp_go_md vnctp_go_md;

VNCTP_GO_EXPORT uint32_t vnctp_go_abi_version(void);
VNCTP_GO_EXPORT const char *vnctp_go_td_sdk_version(void);
VNCTP_GO_EXPORT const char *vnctp_go_md_sdk_version(void);

VNCTP_GO_EXPORT vnctp_go_td *vnctp_go_td_create(const char *flow, int production, uint32_t queue_capacity);
VNCTP_GO_EXPORT int vnctp_go_td_start(vnctp_go_td *, const char *front, int private_topic, int public_topic);
VNCTP_GO_EXPORT int vnctp_go_td_request(vnctp_go_td *, uint32_t request, const void *data, uint32_t size,
                                      int32_t request_id);
VNCTP_GO_EXPORT int vnctp_go_td_front_info(vnctp_go_td *, struct CThostFtdcFrontInfoField *);
VNCTP_GO_EXPORT int vnctp_go_td_trading_day(vnctp_go_td *, TThostFtdcDateType);
VNCTP_GO_EXPORT int vnctp_go_td_poll(vnctp_go_td *, vnctp_go_event *, uint32_t capacity, uint32_t timeout_ms);
VNCTP_GO_EXPORT int vnctp_go_td_stop(vnctp_go_td *);
VNCTP_GO_EXPORT int vnctp_go_td_destroy(vnctp_go_td *);

VNCTP_GO_EXPORT vnctp_go_md *vnctp_go_md_create(const char *flow, int production, uint32_t queue_capacity);
VNCTP_GO_EXPORT int vnctp_go_md_start(vnctp_go_md *, const char *front);
VNCTP_GO_EXPORT int vnctp_go_md_login(vnctp_go_md *, const struct CThostFtdcReqUserLoginField *, int32_t request_id);
VNCTP_GO_EXPORT int vnctp_go_md_subscribe(vnctp_go_md *, const vnctp_go_symbol *, uint32_t count);
VNCTP_GO_EXPORT int vnctp_go_md_unsubscribe(vnctp_go_md *, const vnctp_go_symbol *, uint32_t count);
VNCTP_GO_EXPORT int vnctp_go_md_poll(vnctp_go_md *, vnctp_go_event *, uint32_t capacity, uint32_t timeout_ms);
VNCTP_GO_EXPORT int vnctp_go_md_stop(vnctp_go_md *);
VNCTP_GO_EXPORT int vnctp_go_md_destroy(vnctp_go_md *);

#ifdef __cplusplus
}
#endif

#endif

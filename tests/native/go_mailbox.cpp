#include "mailbox.hpp"

#include <cassert>
#include <future>

using vnctp_go::event;
using vnctp_go::notice;

namespace {

void control_isolation() {
    vnctp_go::Mailbox first(2), second(2);
    CThostFtdcTradeField row{};
    CThostFtdcRspInfoField error{};
    row.Volume = 7;
    error.ErrorID = 3;
    first.push(event(VNCTP_GO_RSP_QRY_TRADE, &row, &error, 11, false));
    row.Volume = 9;
    error.ErrorID = 44;
    second.push(event(VNCTP_GO_RSP_QRY_TRADE, &row, &error, 11, true));
    first.push(event<CThostFtdcTradeField>(VNCTP_GO_RSP_QRY_TRADE, nullptr, nullptr, 11, true));
    vnctp_go_event out[2]{};
    assert(first.poll(out, 2, 0) == 2);
    assert(out[0].kind == VNCTP_GO_RSP_QRY_TRADE && out[0].request_id == 11 && !out[0].is_last);
    assert(out[0].data_size == sizeof(row) && out[0].has_error && out[0].error.ErrorID == 3);
    CThostFtdcTradeField delivered{};
    std::memcpy(&delivered, &out[0].data, sizeof(delivered));
    assert(delivered.Volume == 7);
    assert(out[1].is_last && !out[1].data_size && !out[1].has_error);
    assert(second.poll(out, 2, 0) == 1 && out[0].request_id == 11 && out[0].is_last);
    std::memcpy(&delivered, &out[0].data, sizeof(delivered));
    assert(delivered.Volume == 9 && out[0].error.ErrorID == 44);

    first.push(notice(VNCTP_GO_FRONT_CONNECTED));
    first.push(notice(VNCTP_GO_FRONT_DISCONNECTED, 4097));
    first.push(notice(VNCTP_GO_FRONT_CONNECTED));
    assert(first.poll(out, 2, 0) == VNCTP_GO_OVERFLOW);
    assert(second.poll(out, 2, 0) == 0);
}

void bounded_quotes() {
    vnctp_go::Mailbox market(3, 2);
    const vnctp_go_symbol names[]{{"rb2701"}, {"au2612"}};
    assert(market.reserve(names, 2) == 0);
    assert(market.reserve(names, 1) == -2);
    CThostFtdcDepthMarketDataField row{};
    std::strcpy(row.InstrumentID, names[0].instrument);
    row.LastPrice = std::numeric_limits<double>::max();
    market.quote(&row);
    row.LastPrice = 3000;
    market.quote(&row);
    row.LastPrice = 3001;
    market.quote(&row);
    market.push(notice(VNCTP_GO_FRONT_CONNECTED));
    vnctp_go_event out[3]{};
    assert(market.poll(out, 3, 0) == 2);
    assert(out[0].kind == VNCTP_GO_FRONT_CONNECTED && out[1].kind == VNCTP_GO_RTN_QUOTE);
    CThostFtdcDepthMarketDataField delivered{};
    std::memcpy(&delivered, &out[1].data, sizeof(delivered));
    assert(delivered.LastPrice == 3000 && !std::strcmp(delivered.InstrumentID, names[0].instrument));
    assert(market.poll(out, 3, 0) == 0);

    market.quote(&row);
    CThostFtdcSpecificInstrumentField ack{};
    std::strcpy(ack.InstrumentID, names[0].instrument);
    CThostFtdcRspInfoField rejected{};
    rejected.ErrorID = 19;
    market.push(event(VNCTP_GO_RSP_UNSUBSCRIBE, &ack, &rejected, 1, true));
    assert(market.poll(out, 3, 0) == 2 && out[0].error.ErrorID == 19);
    assert(market.reserve(names, 1) == -2);
    market.quote(&row);
    market.push(event(VNCTP_GO_RSP_UNSUBSCRIBE, &ack, nullptr, 2, true));
    market.quote(&row);
    assert(market.poll(out, 3, 0) == 1 && out[0].kind == VNCTP_GO_RSP_UNSUBSCRIBE && !out[0].has_error);
    assert(market.reserve(names, 1) == 0);

    market.quote(&row);
    market.push(notice(VNCTP_GO_FRONT_DISCONNECTED, 4097));
    assert(market.poll(out, 3, 0) == 1 && out[0].reason == 4097);
    assert(market.reserve(names, 2) == 0);
    market.rollback(names, 2);
    auto waiter = std::async(std::launch::async, [&] { return market.poll(out, 3, 60000); });
    assert(waiter.wait_for(std::chrono::milliseconds(20)) == std::future_status::timeout);
    market.close();
    assert(waiter.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    assert(waiter.get() == VNCTP_GO_CLOSED);
}

} // namespace

int main() {
    control_isolation();
    bounded_quotes();
}

#ifndef VNCTP_GO_MAILBOX_HPP
#define VNCTP_GO_MAILBOX_HPP

#include "vnctp_go.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstring>
#include <limits>
#include <mutex>
#include <vector>

namespace vnctp_go {

template <typename Row>
vnctp_go_event event(uint32_t kind, const Row *row, const CThostFtdcRspInfoField *error = nullptr,
                    int32_t id = 0, bool last = false) {
    static_assert(sizeof(Row) <= sizeof(vnctp_go_payload));
    vnctp_go_event value{};
    value.kind = kind;
    value.request_id = id;
    value.is_last = last;
    if (row) {
        value.data_size = sizeof(Row);
        std::memcpy(&value.data, row, sizeof(Row));
    }
    if (error) {
        value.has_error = 1;
        value.error = *error;
    }
    return value;
}

inline vnctp_go_event notice(uint32_t kind, int32_t reason = 0) {
    vnctp_go_event value{};
    value.kind = kind;
    value.reason = reason;
    return value;
}

class Mailbox {
public:
    explicit Mailbox(uint32_t capacity, uint32_t quote_capacity = 0)
        : controls_(capacity), quotes_(quote_capacity) {}

    int state() {
        std::lock_guard lock(mutex_);
        return state_;
    }

    void push(const vnctp_go_event &value) {
        std::lock_guard lock(mutex_);
        if (state_) return;
        if (value.kind == VNCTP_GO_FRONT_DISCONNECTED) {
            clear_quotes();
        } else if (value.kind == VNCTP_GO_RSP_UNSUBSCRIBE && value.data_size && !value.error.ErrorID) {
            CThostFtdcSpecificInstrumentField row{};
            std::memcpy(&row, &value.data, sizeof(row));
            erase_symbol(row.InstrumentID);
        }
        if (count_ == controls_.size()) {
            // 丢失一个控制事实就废弃整代，不交付可能不完整的查询结果。
            state_ = VNCTP_GO_OVERFLOW;
            count_ = 0;
            clear_quotes();
            changed_.notify_all();
            return;
        }
        controls_[(head_ + count_) % controls_.size()] = value;
        ++count_;
        changed_.notify_one();
    }

    int reserve(const vnctp_go_symbol *symbols, uint32_t count) {
        std::lock_guard lock(mutex_);
        if (state_) return state_;
        if (count > quotes_.size() - active_) return -2;
        for (uint32_t i = 0; i < count; ++i) {
            if (find_symbol(symbols[i].instrument) != quotes_.end()) return VNCTP_GO_BAD_STATE;
        }
        auto current = quotes_.begin();
        for (uint32_t i = 0; i < count; ++i) {
            current = std::find_if(current, quotes_.end(), [](const auto &slot) { return !slot.symbol.instrument[0]; });
            current->symbol = symbols[i];
            ++current;
            ++active_;
        }
        return 0;
    }

    void rollback(const vnctp_go_symbol *symbols, uint32_t count) {
        std::lock_guard lock(mutex_);
        for (uint32_t i = 0; i < count; ++i) erase_symbol(symbols[i].instrument);
    }

    void quote(const CThostFtdcDepthMarketDataField *row) {
        if (!row || !std::isfinite(row->LastPrice)
            || std::abs(row->LastPrice) == std::numeric_limits<double>::max()) return;
        std::lock_guard lock(mutex_);
        if (state_) return;
        const auto slot = find_symbol(row->InstrumentID);
        if (slot == quotes_.end() || slot->ready) return;
        slot->row = *row;
        slot->ready = true;
        ++pending_quotes_;
        changed_.notify_one();
    }

    int poll(vnctp_go_event *output, uint32_t capacity, uint32_t timeout_ms) {
        if (!output || !capacity || capacity > VNCTP_GO_MAX_QUEUE || timeout_ms > 60000) {
            return VNCTP_GO_INVALID;
        }
        std::unique_lock lock(mutex_);
        changed_.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&] {
            return state_ || count_ || pending_quotes_;
        });
        if (state_) return state_;
        uint32_t written = 0;
        while (count_ && written < capacity) {
            output[written++] = controls_[head_];
            head_ = (head_ + 1) % controls_.size();
            --count_;
        }
        if (pending_quotes_) {
            for (auto &slot : quotes_) {
                if (written == capacity) break;
                if (slot.ready) {
                    output[written++] = event(VNCTP_GO_RTN_QUOTE, &slot.row);
                    slot.ready = false;
                    --pending_quotes_;
                }
            }
        }
        return static_cast<int>(written);
    }

    void close() {
        std::lock_guard lock(mutex_);
        state_ = VNCTP_GO_CLOSED;
        count_ = 0;
        clear_quotes();
        changed_.notify_all();
    }

private:
    struct Slot {
        vnctp_go_symbol symbol{};
        CThostFtdcDepthMarketDataField row{};
        bool ready = false;
    };

    std::vector<Slot>::iterator find_symbol(const char *name) {
        return std::find_if(quotes_.begin(), quotes_.end(), [&](const Slot &slot) {
            return slot.symbol.instrument[0]
                && !std::strncmp(name, slot.symbol.instrument, sizeof(slot.symbol.instrument));
        });
    }

    void erase_symbol(const char *name) {
        const auto slot = find_symbol(name);
        if (slot == quotes_.end()) return;
        pending_quotes_ -= slot->ready;
        slot->ready = false;
        slot->symbol = {};
        --active_;
    }

    void clear_quotes() {
        for (auto &slot : quotes_) {
            slot.symbol = {};
            slot.ready = false;
        }
        active_ = pending_quotes_ = 0;
    }

    std::mutex mutex_;
    std::condition_variable changed_;
    std::vector<vnctp_go_event> controls_;
    std::vector<Slot> quotes_;
    size_t head_ = 0;
    size_t count_ = 0;
    size_t active_ = 0;
    size_t pending_quotes_ = 0;
    int state_ = 0;
};

} // namespace vnctp_go

#endif

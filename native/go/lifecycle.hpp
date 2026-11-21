#ifndef VNCTP_GO_LIFECYCLE_HPP
#define VNCTP_GO_LIFECYCLE_HPP

#include "mailbox.hpp"

#include <array>
#include <memory>

namespace vnctp_go {

template <typename Api>
class Handle {
public:
    explicit Handle(uint32_t capacity, uint32_t quotes = 0) : inbox(capacity, quotes) {}

    void own(Api *api) { api_ = api; }

    template <typename Spi, typename Configure>
    int start(Spi *spi, const char *front, Configure configure) {
        if (!front || !front[0] || strnlen(front, front_.size()) == front_.size()) {
            return VNCTP_GO_INVALID;
        }
        std::lock_guard lock(commands_);
        if (!api_) return VNCTP_GO_CLOSED;
        if (started_ || init_attempted_ || poisoned_) return VNCTP_GO_BAD_STATE;
        std::memcpy(front_.data(), front, std::strlen(front) + 1);
        try {
            configure(*api_);
            api_->RegisterSpi(spi);
            api_->RegisterFront(front_.data());
            init_attempted_ = true;
            api_->Init();
            started_ = true;
            return 0;
        } catch (...) {
            poisoned_ = true;
            inbox.close();
            return VNCTP_GO_NATIVE_FAILURE;
        }
    }

    template <typename Command>
    int send(Command command) {
        std::lock_guard lock(commands_);
        if (const int failed = inbox.state()) return failed;
        if (!api_) return VNCTP_GO_CLOSED;
        if (!started_ || poisoned_) return VNCTP_GO_BAD_STATE;
        try {
            return command(*api_);
        } catch (...) {
            poisoned_ = true;
            inbox.close();
            return VNCTP_GO_NATIVE_FAILURE;
        }
    }

    int stop() {
        std::lock_guard lock(commands_);
        if (release_failed_) return VNCTP_GO_NATIVE_FAILURE;
        inbox.close();
        if (!api_) return 0;
        try {
            api_->RegisterSpi(nullptr);
            // 6.7.13 的内部线程必须初始化，才能执行 Release。
            if (!init_attempted_) {
                init_attempted_ = true;
                api_->Init();
            }
            api_->Release();
            api_ = nullptr;
            return 0;
        } catch (...) {
            release_failed_ = true;
            return VNCTP_GO_NATIVE_FAILURE;
        }
    }

    bool released() {
        std::lock_guard lock(commands_);
        return api_ == nullptr;
    }

    Mailbox inbox;

private:
    std::mutex commands_;
    Api *api_ = nullptr;
    std::array<char, 512> front_{};
    bool started_ = false;
    bool init_attempted_ = false;
    bool poisoned_ = false;
    bool release_failed_ = false;
};

template <typename HandleType, typename Factory>
HandleType *create(const char *flow, int production, uint32_t capacity, Factory factory) noexcept {
    if (!flow || !flow[0] || (production != 0 && production != 1) || !capacity
        || capacity > VNCTP_GO_MAX_QUEUE) return nullptr;
    try {
        auto handle = std::make_unique<HandleType>(capacity);
        auto *api = factory(flow, production != 0);
        if (!api) return nullptr;
        handle->owner.own(api);
        return handle.release();
    } catch (...) {
        return nullptr;
    }
}

template <typename HandleType, typename Operation>
int call(HandleType *handle, Operation operation) noexcept {
    if (!handle) return VNCTP_GO_INVALID;
    try {
        return operation(*handle);
    } catch (...) {
        return VNCTP_GO_NATIVE_FAILURE;
    }
}

template <typename HandleType>
int destroy(HandleType *handle) {
    return call(handle, [](auto &value) -> int {
        if (!value.owner.released()) return VNCTP_GO_BAD_STATE;
        delete &value;
        return 0;
    });
}

} // namespace vnctp_go

#endif

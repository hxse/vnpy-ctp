#include "vnctp.h"

struct Payload
{
    atomic<int>& alive;
    explicit Payload(atomic<int>& value) : alive(value) { ++alive; }
    ~Payload() { --alive; }
};

PYBIND11_MODULE(_native_probe, module)
{
    module.def("decode", [](pybind11::bytes bytes) {
        return toUtf(bytes.cast<string>());
    });
    module.def("queue_lifetime", []() {
        atomic<int> alive{0};
        TaskQueue queue;
        {
            Task task{};
            task.task_data = make_shared<Payload>(alive);
            queue.push(task);
        }
        int queued = alive;
        queue.terminate();
        int discarded = alive;
        // 终止后的迟到回调不得重新积压到队列，且要释放原生数据。
        thread producer([&]() {
            for (int index = 0; index < 1000; ++index) {
                Task task{};
                task.task_error = make_shared<Payload>(alive);
                queue.push(task);
            }
        });
        producer.join();
        bool terminated = false;
        try { queue.pop(); } catch (const TerminatedError&) { terminated = true; }
        pybind11::dict result;
        result["queued"] = queued;
        result["discarded"] = discarded;
        result["remaining"] = alive.load();
        result["terminated"] = terminated;
        return result;
    });
}

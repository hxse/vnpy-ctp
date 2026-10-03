#include "pybind11/pybind11.h"
#include <stdexcept>
#include <atomic>
#include <memory>
#include <string>
#include <queue>
#include <thread>
#include <mutex>
#include <iostream>
#include <codecvt>
#include <condition_variable>
#include <locale>




using namespace std;
using namespace pybind11;


//任务结构体
struct Task
{
    int task_name;		//回调函数名称对应的常数
    shared_ptr<void> task_data;	//任务指针
    shared_ptr<void> task_error;	//错误指针
    int task_id;		//任务id
    bool task_last;		//是否为最后返回
};

class TerminatedError : std::exception
{};

class TaskQueue
{
private:
    queue<Task> queue_;						//标准队列
    mutex mutex_;							//锁
    condition_variable cond_;				//条件变量

    bool _terminate = false;

public:

    //存入新的任务
    void push(const Task &task)
    {
        unique_lock<mutex > mlock(mutex_);
        if (_terminate)
            return;
        queue_.push(task);					//存入任务后写入队列
        mlock.unlock();						//释放锁
        cond_.notify_one();					//通知正在等待的线程
    }

    //取出最早的任务
    Task pop()
    {
        unique_lock<mutex> mlock(mutex_);
        cond_.wait(mlock, [&]() {
            return !queue_.empty() || _terminate;
        });				//等待条件变量通知
        if (_terminate)
            throw TerminatedError();
        Task task = queue_.front();			//获取队列中最早的一个任务
        queue_.pop();						//删除任务
        return task;						//返回该任务
    }

    void terminate()
    {
        queue<Task> discarded;
        {
            unique_lock<mutex> mlock(mutex_);
            _terminate = true;
            discarded.swap(queue_);
        }
        cond_.notify_all();					//通知正在等待的线程
    }
};


//从字典中获取某个键值对应的整数，并将其赋值到请求结构体对象上
void getInt(const dict &d, const char *key, int *value)
{
    if (d.contains(key))		//检查键值是否存在该键值
    {
        object o = d[key];		//获取该键值
        *value = o.cast<int>();
    }
};


//从字典中获取某个键值对应的浮点数，并将其赋值到请求结构体对象上
void getDouble(const dict &d, const char *key, double *value)
{
    if (d.contains(key))
    {
        object o = d[key];
        *value = o.cast<double>();
    }
};


//从字典中获取某个键值对应的字符，并将其赋值到请求结构体对象上
void getChar(const dict &d, const char *key, char *value)
{
    if (d.contains(key))
    {
        object o = d[key];
        *value = o.cast<char>();
    }
};


template <size_t size>
using string_literal = char[size];

//从字典中获取某个键值对应的字符串，并将其赋值到请求结构体对象上
template <size_t size>
void getString(const pybind11::dict &d, const char *key, string_literal<size> &value)
{
    if (d.contains(key))
    {
        object o = d[key];
        string s = o.cast<string>();
        const char *buf = s.c_str();
        strcpy(value, buf);
    }
};


//将GBK编码的字符串转换为UTF8
inline string toUtf(const string &gb2312)
{
    // Callers hold the GIL. Decode without requiring an OS GB18030 locale.
    PyObject *decoded = PyUnicode_Decode(
        gb2312.data(), gb2312.size(), "gb18030", "replace"
    );
    if (!decoded)
        throw error_already_set();
    return reinterpret_steal<str>(decoded).cast<string>();
}

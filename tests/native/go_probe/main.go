package main

/*
#include <stdlib.h>
#include "vnctp_go.h"
*/
import "C"

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unsafe"
)

func check(ok bool, message string) {
	if !ok {
		panic(message)
	}
}

func flow(root, key string) *C.char {
	path := filepath.Join(root, key)
	if err := os.Mkdir(path, 0700); err != nil {
		panic(err)
	}
	return C.CString(path + string(os.PathSeparator))
}

func trade(root string) {
	path := flow(root, "trade")
	defer C.free(unsafe.Pointer(path))
	handle := C.vnctp_go_td_create(path, 1, 8)
	check(handle != nil, "TdApi 创建")
	check(C.vnctp_go_td_destroy(handle) == C.VNCTP_GO_BAD_STATE, "释放前拒绝销毁")
	var row C.struct_CThostFtdcQryInstrumentField
	size := C.uint32_t(C.sizeof_struct_CThostFtdcQryInstrumentField)
	check(C.vnctp_go_td_request(handle, C.VNCTP_GO_REQ_QRY_INSTRUMENT, unsafe.Pointer(&row), size, 1) == C.VNCTP_GO_BAD_STATE,
		"初始化前拒绝请求")
	front := C.CString("tcp://127.0.0.1:1")
	defer C.free(unsafe.Pointer(front))
	check(C.vnctp_go_td_start(handle, front, 2, 0) == 0, "TdApi 初始化")
	check(C.vnctp_go_td_start(handle, front, 2, 0) == C.VNCTP_GO_BAD_STATE, "重复初始化被拒绝")
	check(C.vnctp_go_td_request(handle, C.VNCTP_GO_REQ_QRY_INSTRUMENT, unsafe.Pointer(&row), size-1, 1) == C.VNCTP_GO_INVALID,
		"提交前校验请求结构体")
	check(C.vnctp_go_td_request(handle, C.VNCTP_GO_REQ_QRY_INSTRUMENT, unsafe.Pointer(&row), size, 1) == -1,
		"未连接查询保留 SDK 的返回值")
	check(C.vnctp_go_td_stop(handle) == 0 && C.vnctp_go_td_stop(handle) == 0, "交易真实释放及重复停止")
	check(C.vnctp_go_td_destroy(handle) == 0, "交易句柄销毁")
}

func market(root string) {
	path := flow(root, "market")
	defer C.free(unsafe.Pointer(path))
	handle := C.vnctp_go_md_create(path, 0, 8)
	check(handle != nil, "MdApi 创建")
	check(C.vnctp_go_md_subscribe(handle, nil, 0) == C.VNCTP_GO_INVALID, "空订阅被拒绝")
	var out C.vnctp_go_event
	check(C.vnctp_go_md_poll(handle, &out, 1, 0) == 0, "空队列不返回旧事件")
	read := make(chan C.int, 1)
	go func() {
		var event C.vnctp_go_event
		read <- C.vnctp_go_md_poll(handle, &event, 1, 5000)
	}()
	select {
	case <-read:
		panic("等待未阻塞")
	case <-time.After(20 * time.Millisecond):
	}
	check(C.vnctp_go_md_stop(handle) == 0, "未 Init 的行情 API 真实释放")
	select {
	case result := <-read:
		check(result == C.VNCTP_GO_CLOSED, "停止唤醒 poll")
	case <-time.After(time.Second):
		panic("停止后 poll 未退出")
	}
	check(C.vnctp_go_md_destroy(handle) == 0, "行情句柄销毁")
}

func main() {
	check(len(os.Args) == 3, "需要测试目录和厂商构建串")
	check(C.vnctp_go_abi_version() == C.VNCTP_GO_ABI_VERSION, "ABI 版本一致")
	td, md := C.GoString(C.vnctp_go_td_sdk_version()), C.GoString(C.vnctp_go_md_sdk_version())
	check(strings.HasPrefix(td, "v6.7.13_") && td == os.Args[2] && md == os.Args[2], "交易与行情的厂商构建一致")
	trade(os.Args[1])
	market(os.Args[1])
	fmt.Println("CTP Go C ABI, 6.7.13 SDK, request validation and release verified")
}

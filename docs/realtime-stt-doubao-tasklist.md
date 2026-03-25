# Realtime STT 改造任务单

## 背景

当前链路是：

`按住录音 -> 松手 -> 生成完整 WAV -> 上传到 OpenClaw transcription route -> 子项目本地 whisper/OpenClaw runtime 转写 -> 再调用 /v1/responses`

这个模式的主要问题不是 LLM 慢，而是 STT 必须等待整段录音结束后才能开始处理，导致：

- 用户体感“说完之后还要再等一段”
- Pi 端无法显示实时字幕
- OpenClaw 端无法尽早拿到确定文本

本次目标是把 STT 改为“流式识别”，优先接入豆包实时 ASR，由 OpenClaw 子项目负责桥接，主项目继续只依赖 OpenClaw。

## 目标

- 让 Pi 在说话过程中就能收到 partial transcript
- 用户松手后尽快拿到 final transcript
- final transcript 仍由主项目送入 OpenClaw `/v1/responses`
- 不把豆包鉴权信息放到 Pi 上
- 保留当前 one-shot transcription 作为 fallback

## 非目标

- 本版本不做“边说边把 partial transcript 直接送给 LLM”
- 本版本不替换现有 `/v1/audio/speech` TTS 链路
- 本版本不移除现有 `/v1/audio/transcriptions` 一次性接口

## 推荐架构

推荐链路：

`Pi -> OpenClaw 插件 realtime STT route -> 豆包 realtime ASR -> OpenClaw 插件 -> Pi`

拿到 final transcript 后：

`Pi -> OpenClaw /v1/responses -> 流式回复 -> Pi 显示/TTS`

这样做的原因：

- Pi 端只依赖 OpenClaw，供应商切换成本最低
- 豆包密钥只放在 OpenClaw 主机
- 鉴权、日志、限流、降级都集中在子项目
- 后续如果改成别的实时 ASR，主项目接口可以不变

## 当前代码切入点

主项目关键位置：

- `record_audio.py`: 当前只支持完整 WAV 录制
- `main.py`: 当前在按钮松开后才调用 `transcribe(wav_path)`
- `transcribe_openai.py`: 当前只支持一次性上传文件转写

子项目关键位置：

- `openclaw-macos-say-tts-plugin/index.ts`: 当前只实现 `/v1/audio/transcriptions` 一次性上传
- `openclaw-macos-say-tts-plugin/openclaw.plugin.json`: 当前 transcription backend 只有 `local-whisper` 和 `openclaw-runtime`
- `openclaw-macos-say-tts-plugin/index.test.mjs`: 当前已有 transcription route 单测，可扩展为 realtime route 测试

## 接口合同草案

### 1. Pi -> OpenClaw realtime STT

推荐新接口：

- `GET/WS /plugins/macos-say-tts/asr/realtime`

鉴权：

- 复用 OpenClaw gateway token
- 连接时带 `Authorization: Bearer <OPENCLAW_TOKEN>`

客户端发送事件：

1. `session.start`
2. `audio.append`
3. `session.commit`
4. `session.cancel`

建议 JSON 事件结构：

```json
{
  "type": "session.start",
  "audio_format": "pcm_s16le",
  "sample_rate": 16000,
  "channels": 1,
  "language": "zh",
  "enable_partial": true
}
```

```json
{
  "type": "audio.append",
  "audio_base64": "<base64 PCM chunk>",
  "sequence": 12,
  "duration_ms": 100
}
```

```json
{
  "type": "session.commit"
}
```

OpenClaw 返回事件：

```json
{
  "type": "session.started",
  "session_id": "..."
}
```

```json
{
  "type": "transcript.partial",
  "text": "你好，我想问",
  "utterance_id": "u1"
}
```

```json
{
  "type": "transcript.final",
  "text": "你好，我想问一下今天的天气。",
  "utterance_id": "u1"
}
```

```json
{
  "type": "session.completed",
  "final_text": "你好，我想问一下今天的天气。"
}
```

```json
{
  "type": "error",
  "code": "upstream_timeout",
  "message": "..."
}
```

说明：

- 第一版统一走 JSON 文本帧，方便调试和单测
- 即使豆包上游是二进制协议，Pi 与 OpenClaw 之间先保持可读性优先
- 如果后面确认 Pi 端 CPU/带宽吃紧，再把 `audio.append` 改成二进制帧

### 2. OpenClaw -> 豆包 realtime ASR

子项目负责：

- 建立到豆包 realtime ASR 的 WebSocket 连接
- 按官方协议发送 session 初始化参数
- 把 Pi 送来的音频 chunk 转成豆包要求的请求包
- 把豆包返回的 partial/final 结果映射成本项目统一事件

建议豆包配置先固定为：

- 16k
- 单声道
- PCM 16-bit little-endian
- chunk 时长 100ms
- `show_utterances=true`
- 使用 VAD
- 输出 single result，便于逐句确认

### 3. one-shot fallback

保留现有：

- `POST /v1/audio/transcriptions`

回退条件：

- realtime route 连接失败
- 豆包鉴权失败或限流
- realtime session 中途断线
- Pi 端显式配置 `STT_MODE=oneshot`

## 主项目详细任务

### Phase 1: 抽象 STT 客户端

- 新增 `stt_client.py` 统一接口
- 定义 `OneShotSttClient` 和 `RealtimeSttClient`
- 让 `main.py` 只依赖抽象接口，不直接 import `transcribe_openai.transcribe`

建议接口：

```python
class RealtimeTranscriptEvent(TypedDict):
    type: Literal["partial", "final", "completed", "error"]
    text: str

class BaseSttClient(Protocol):
    def start(self) -> None: ...
    def append_audio(self, pcm_chunk: bytes) -> None: ...
    def commit(self) -> str: ...
    def cancel(self) -> None: ...
```

任务项：

- 从 `transcribe_openai.py` 保留 one-shot 实现
- 新建 `transcribe_realtime.py`
- 新建最小事件队列或回调机制，供 UI 消费 partial transcript

### Phase 2: 录音器支持 chunk 推流

- 改造 `record_audio.py`
- 不再只依赖完整文件落盘
- 新增“边录边读”的 PCM 输出能力

推荐实现：

- 继续使用 `arecord`
- 但输出改成 stdout PCM 流
- 主线程或后台线程按固定 chunk 读取
- 同时可选写入 `/tmp/utterance.wav` 作为 debug/fallback 产物

建议新增能力：

- `Recorder.start_streaming()`
- `Recorder.iter_pcm_chunks(chunk_ms=100)`
- `Recorder.stop_streaming()`
- `Recorder.save_debug_wav()` 可选

### Phase 3: 主状态机接入 realtime STT

- 按钮按下时：
  - 建立 realtime STT session
  - 开始录音
  - 开始向 STT 推送 chunk
- 录音过程中：
  - UI 显示 partial transcript
  - 保留静音检测逻辑，但改为“录制中 RMS 观察”而不是只在 stop 后检查
- 按钮松开时：
  - 停止采集新音频
  - 发送 `session.commit`
  - 等待 `final_text`
  - final 为空时回 idle
  - final 非空时继续调用 `/v1/responses`

对应文件：

- `main.py`
- `record_audio.py`
- `display.py`
- `button_ptt.py`

### Phase 4: UI 与交互

新增 UI 状态建议：

- `Listening...`
- `Listening: partial transcript`
- `Finishing speech...`
- `Thinking...`

具体任务：

- partial transcript 需要单独显示区域
- partial 更新要限频，避免 LCD 刷得太快
- final transcript 成功后再清空 partial
- 取消时要立刻停止录音线程与 STT session

### Phase 5: 配置与降级

`config.py` 新增建议配置：

- `STT_MODE=realtime|oneshot`
- `REALTIME_STT_BASE_URL`
- `REALTIME_STT_HTTP_PATH=/plugins/macos-say-tts/asr/realtime`
- `REALTIME_STT_API_TOKEN`
- `REALTIME_STT_LANGUAGE`
- `REALTIME_STT_CHUNK_MS=100`
- `REALTIME_STT_CONNECT_TIMEOUT_SECONDS`
- `REALTIME_STT_COMMIT_TIMEOUT_SECONDS`
- `REALTIME_STT_SHOW_PARTIAL=true`
- `REALTIME_STT_FALLBACK_TO_ONESHOT=true`

降级策略：

- realtime 初始化失败，自动 fallback 到 one-shot
- commit 超时，自动 fallback 到 one-shot
- 用户取消时，两个链路都要能安全退出

## 子项目详细任务

### Phase 1: 扩展配置 schema

在 `openclaw.plugin.json` 增加：

- `transcriptionBackend` 枚举增加 `doubao-realtime`
- `doubaoAppId`
- `doubaoAccessToken`
- `doubaoWsUrl`
- `doubaoResourceId`
- `doubaoLanguage`
- `doubaoChunkMs`
- `doubaoEnableVad`
- `doubaoVadStartSilenceMs`
- `doubaoVadEndSilenceMs`
- `realtimeSessionTimeoutSeconds`
- `realtimeIdleTimeoutSeconds`
- `realtimeMaxAudioSeconds`

UI hints 要写清楚：

- 哪些是豆包必填
- 哪些是高级调优项
- 默认值和推荐值

### Phase 2: realtime bridge 服务

在 `index.ts` 中新增模块职责：

- `createRealtimeAsrHandler(...)`
- `DoubaoRealtimeClient`
- `RealtimeSessionManager`

职责拆分：

- `createRealtimeAsrHandler`
  - 处理 Pi 接入
  - 鉴权
  - session 生命周期
- `DoubaoRealtimeClient`
  - 负责与豆包 WebSocket 通信
  - 负责协议编解码
- `RealtimeSessionManager`
  - 维护 session 状态
  - 聚合 partial/final 文本
  - 超时清理

### Phase 3: 豆包结果映射

映射规则建议：

- 豆包 interim -> `transcript.partial`
- 豆包 definite utterance -> `transcript.final`
- 豆包最终结束事件 -> `session.completed`
- 豆包错误码 -> `error`

状态维护：

- `partialText`: 当前未确认文本
- `finalSegments[]`: 已确认句子
- `finalText`: `finalSegments.join("")`

### Phase 4: 兼容现有 one-shot route

- 现有 `/v1/audio/transcriptions` 不删
- `doubao-realtime` 不应影响 `local-whisper` 和 `openclaw-runtime`
- 如果插件启动时 realtime 配置不完整，仍可只提供 one-shot route

### Phase 5: 可观测性

子项目新增日志：

- realtime session started
- upstream doubao connected
- first partial latency
- first final latency
- total audio duration
- final transcript length
- upstream close code / reason

健康检查可扩展返回：

- `realtimeEnabled`
- `realtimeBackend`
- `realtimeWsConfigured`

## 单元测试任务单

本次改造不能只靠联调，要先把最容易回归的协议层和状态机层覆盖住。

### 子项目单测

继续使用现有 `node:test`，扩展 `openclaw-macos-say-tts-plugin/index.test.mjs`。

新增测试项：

- 注册了 realtime route
- 缺少鉴权 header 时拒绝连接
- `session.start` 参数非法时返回 400/错误事件
- 正常 session 能接收多段 `audio.append`
- 上游返回 partial 时，插件向下游发 `transcript.partial`
- 上游返回 final 时，插件向下游发 `transcript.final`
- `session.commit` 后能输出 `session.completed`
- 上游报错时能映射为统一 `error`
- realtime backend 未配置时 route 返回清晰错误
- one-shot transcription route 仍保持现有行为不回归

推荐做法：

- 把豆包客户端抽成可注入 mock
- 单测里不要真的连豆包
- 通过 fake event emitter 模拟 partial/final/error

### 主项目单测

主项目目前还没有测试基础设施，本次建议补最小 `pytest`。

新增测试文件建议：

- `tests/test_transcribe_realtime.py`
- `tests/test_main_realtime_flow.py`
- `tests/test_record_audio_streaming.py`

新增测试项：

- realtime 客户端能正确发送 `session.start`
- `append_audio` 会按顺序发送 chunk
- `commit()` 能等待 final transcript 并返回文本
- partial transcript 到达时会更新内部缓冲
- realtime 失败时能 fallback 到 one-shot
- 用户取消时会关闭 session 且不再继续推送音频
- 松手后无 final transcript 时回到 idle
- final transcript 成功时会继续调用 `stream_response()`

推荐做法：

- 主项目通过 mock WebSocket 客户端测试，不依赖真实网络
- `main.py` 里把 STT client、display、openclaw response client 做依赖注入
- 录音 chunk 生成器用 fake bytes，不在单测里启动 `arecord`

## 联调与验收标准

### 联调顺序

1. 子项目单独 mock 豆包，跑通 Pi 下游协议
2. 子项目真连豆包，验证 partial/final 映射
3. 主项目接 mock realtime STT 服务，验证 UI/状态机
4. 主项目接真实 OpenClaw realtime route
5. 最后回归 `/v1/responses` 与 `/v1/audio/speech`

### 关键验收指标

- 按下说话后 1 秒内应看到第一条 partial transcript
- 松手后 final transcript 明显快于现有 one-shot 模式
- 取消操作不会留下僵尸录音进程或悬挂 session
- realtime 失败时系统能自动回退到 one-shot
- 不影响现有 TTS 和 `/v1/responses` 链路

### 建议打点

主项目：

- `stt_realtime_connect_ms`
- `stt_first_partial_ms`
- `stt_final_ms`
- `llm_first_token_ms`

子项目：

- `doubao_connect_ms`
- `doubao_first_partial_ms`
- `doubao_final_ms`
- `session_audio_chunks`

## 实施顺序建议

建议按以下顺序做，风险最低：

1. 子项目先做 mockable realtime bridge 骨架和单测
2. 子项目接入豆包协议并验证 partial/final 映射
3. 主项目新增 realtime STT client 和配置
4. 主项目改造录音为 chunk 推流
5. 主项目接 UI partial transcript
6. 做 fallback、超时、取消逻辑
7. 跑单测和真机联调

## 风险与待确认项

### P0 待确认

- OpenClaw 当前插件 SDK 是否方便直接承载 WebSocket upgrade
- 如果不方便，是否需要在子项目中额外起一个本地 sidecar realtime bridge

### P1 风险

- Pi Zero 上 base64 + WebSocket 文本帧是否会造成额外 CPU 开销
- LCD 刷新频率过高可能导致 UI 卡顿
- 豆包 VAD 切句方式可能与“按住说话，松手结束”交互产生冲突

### 风险缓解

- 第一版先优先稳定性，不追求极限低延迟
- Pi 与 OpenClaw 之间先用文本帧，验证后再评估二进制帧
- 保留 one-shot fallback，确保可回滚

## 本次开发完成定义

满足以下条件后，视为本轮改造完成：

- 主项目支持 realtime STT 模式与 one-shot fallback
- 子项目支持 `doubao-realtime` backend
- 主项目和子项目都有新增单测
- 现有 one-shot transcription 行为不回归
- 真机联调能稳定看到 partial transcript，并在松手后得到 final transcript

## 参考资料

- 豆包语音技术文档目录: https://www.volcengine.com/docs/6561/80818?lang=zh
- 豆包语音产品简介目录: https://www.volcengine.com/docs/6561/1354871?lang=zh
- OpenClaw Talk Mode: https://docs.openclaw.ai/nodes/talk

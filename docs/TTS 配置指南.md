# 讯飞 TTS 语音合成配置指南

## 配置步骤

### 1. 创建讯飞应用

1. 访问 [讯飞开放平台 - 在线语音合成](https://www.xfyun.cn/doc/tts/online_tts/API.html)
2. 登录讯飞账号（没有账号请先注册）
3. 进入控制台，创建新应用
4. 选择"在线语音合成（流式）"服务
5. 记录生成的凭据：
   - `APP_ID`
   - `API_KEY`
   - `API_SECRET`

### 2. 配置项目

在项目根目录创建或编辑 `.env` 文件：

```bash
# 讯飞 TTS 语音合成
TTS_APP_ID=你的 app_id
TTS_API_KEY=你的 api_key
TTS_API_SECRET=你的 api_secret
TTS_WS_URL=wss://tts-api.xfyun.cn/v2/tts
```

### 3. 选择音色

根据控制台显示的可用音色进行配置。常用音色参数：

| 音色参数名 | 名称 | 性别 | 说明 |
|-----------|------|------|------|
| x4_xiaoyan | 小燕 | 女 | 通用女声（推荐） |
| x4_xiaoyu | 小宇 | 男 | 通用男声 |
| x4_xiaoyuan | 小研 | 女 | 知性女声 |
| x4_xiaofeng | 小峰 | 男 | 成熟男声 |
| x4_xiaomei | 小梅 | 女 | 甜美女声 |
| x4_xiaomeng | 小梦 | 女 | 温柔女声 |

**注意**：具体可用音色请以控制台显示为准，部分音色可能需要单独开通。

### 4. 测试配置

运行测试脚本验证配置：

```bash
python scripts/test_tts_config.py
```

如果测试通过，会生成 `test_tts_output.mp3` 文件。

## API 参数说明

### 在线语音合成（流式）API

- **接口地址**: `wss://tts-api.xfyun.cn/v2/tts`
- **协议**: WebSocket
- **鉴权方式**: HMAC-SHA256 签名

### 请求参数

```json
{
  "common": {
    "app_id": "你的 APP_ID"
  },
  "business": {
    "aue": "lame",           // 音频编码格式：lame=MP3
    "sfl": 1,                // 是否流式传输（必需）
    "auf": "audio/L16;rate=16000",  // 音频采样率
    "vcn": "x4_xiaoyan",     // 音色参数名
    "speed": 50,             // 语速 (0-100)
    "volume": 50,            // 音量 (0-100)
    "pitch": 50,             // 音调 (0-100)
    "tte": "utf8"            // 文本编码
  },
  "data": {
    "status": 2,
    "text": "base64 编码的文本"
  }
}
```

### 响应格式

```json
{
  "code": 0,
  "message": "",
  "data": {
    "audio": "base64 编码的音频数据",
    "status": 2  // 2 表示最后一片
  }
}
```

## 常见问题

### 1. 错误码 10404（APPID 为空）

**原因**: `common.app_id` 未填写或为空  
**解决**: 检查 `.env` 中的 `TTS_APP_ID` 是否正确填写

### 2. 错误码 10401（鉴权失败）

**原因**: API_KEY 或 API_SECRET 错误  
**解决**: 重新检查控制台凭据，确保复制正确

### 3. 错误码 10400（参数非法）

**原因**: 音色参数名不正确  
**解决**: 使用控制台已开启的音色，参数名格式为 `x4_xxx`

### 4. 未返回音频数据

**原因**: 
- 账号欠费或套餐包用尽
- 音色未开通
- 文本内容为空

**解决**: 
- 检查账号余额
- 在控制台开通对应音色
- 确保文本不为空

## 前端配置

前端组件 `VoiceLearning.vue` 中的音色配置：

```typescript
const voices = [
  { key: 'x4_xiaoyan', label: '小燕', gender: '女', emoji: '👩' },
  { key: 'x4_xiaoyu', label: '小宇', gender: '男', emoji: '👨' },
  { key: 'x4_xiaoyuan', label: '小研', gender: '女', emoji: '👩‍' },
  { key: 'x4_xiaofeng', label: '小峰', gender: '男', emoji: '💻' },
]
```

**注意**: 前端音色参数名必须与后端一致，使用 `x4_` 前缀。

## 相关文档

- [讯飞 TTS 在线语音合成 API 文档](https://www.xfyun.cn/doc/tts/online_tts/API.html)
- [讯飞控制台](https://console.xfyun.cn/services/tts)
- [WebSocket 鉴权说明](https://www.xfyun.cn/document/Signature)

## 技术支持

如遇到问题，请检查：
1. 讯飞账号状态（是否欠费）
2. 应用服务状态（是否开通 TTS 服务）
3. 音色状态（是否已开启）
4. 网络连接（是否能访问讯飞 API）

export interface PcmWavRecorder {
  stop: () => Promise<Blob>
  cancel: () => Promise<void>
}

const TARGET_SAMPLE_RATE = 16000

type WindowWithWebkitAudio = Window & {
  webkitAudioContext?: typeof AudioContext
}

export async function createPcmWavRecorder(): Promise<PcmWavRecorder> {
  const AudioContextCtor = window.AudioContext || (window as WindowWithWebkitAudio).webkitAudioContext
  if (!AudioContextCtor) {
    throw new Error('当前浏览器不支持音频录制')
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const audioContext = new AudioContextCtor()
  const source = audioContext.createMediaStreamSource(stream)
  const processor = audioContext.createScriptProcessor(4096, 1, 1)
  const silentGain = audioContext.createGain()
  const chunks: Float32Array[] = []
  let stopped = false

  silentGain.gain.value = 0
  processor.onaudioprocess = (event) => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
  }

  source.connect(processor)
  processor.connect(silentGain)
  silentGain.connect(audioContext.destination)

  async function cleanup() {
    processor.disconnect()
    source.disconnect()
    silentGain.disconnect()
    stream.getTracks().forEach(track => track.stop())
    if (audioContext.state !== 'closed') {
      await audioContext.close()
    }
  }

  return {
    async stop() {
      if (stopped) {
        return new Blob([], { type: 'audio/wav' })
      }
      stopped = true
      await cleanup()
      const samples = mergeFloat32Arrays(chunks)
      const resampled = resample(samples, audioContext.sampleRate, TARGET_SAMPLE_RATE)
      return encodeWav(resampled, TARGET_SAMPLE_RATE)
    },
    async cancel() {
      if (stopped) return
      stopped = true
      chunks.length = 0
      await cleanup()
    },
  }
}

function mergeFloat32Arrays(chunks: Float32Array[]): Float32Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const result = new Float32Array(totalLength)
  let offset = 0
  for (const chunk of chunks) {
    result.set(chunk, offset)
    offset += chunk.length
  }
  return result
}

function resample(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) return input
  const ratio = inputRate / outputRate
  const outputLength = Math.max(1, Math.floor(input.length / ratio))
  const output = new Float32Array(outputLength)

  for (let i = 0; i < outputLength; i++) {
    const inputIndex = i * ratio
    const before = Math.floor(inputIndex)
    const after = Math.min(before + 1, input.length - 1)
    const weight = inputIndex - before
    output[i] = input[before] * (1 - weight) + input[after] * weight
  }

  return output
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const bytesPerSample = 2
  const blockAlign = bytesPerSample
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample)
  const view = new DataView(buffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * bytesPerSample, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, 16, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, samples.length * bytesPerSample, true)

  let offset = 44
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
    offset += bytesPerSample
  }

  return new Blob([view], { type: 'audio/wav' })
}

function writeAscii(view: DataView, offset: number, text: string) {
  for (let i = 0; i < text.length; i++) {
    view.setUint8(offset + i, text.charCodeAt(i))
  }
}

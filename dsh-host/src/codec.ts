/**
 * 帧编解码：4 字节大端长度前缀 + UTF-8 JSON（与 Go 侧 proto.Codec 等价）。
 *
 * 设计要点：
 * - Decoder 是增量式的 —— TCP/stdio 的 chunk 边界与帧边界无关，
 *   push() 任意切分的字节流都必须正确还原帧；
 * - 畸形输入（零长帧、超限帧、非 JSON、版本不符、缺 id/type）抛 ProtoError，
 *   与 Go 侧拒绝行为一一对应；
 * - encode 单帧原子写，长度上限 16 MiB。
 */

import {
  Frame,
  MAX_FRAME_SIZE,
  PROTOCOL_VERSION,
  ProtoError,
} from "./protocol.js";

const HEADER_SIZE = 4;

/** 将一帧编码为 [len:u32be][json] 缓冲。 */
export function encodeFrame(f: Frame): Buffer {
  const body = Buffer.from(JSON.stringify(f), "utf8");
  if (body.length > MAX_FRAME_SIZE) {
    throw new ProtoError(
      "malformed_frame",
      `encoded frame of ${body.length} bytes exceeds limit ${MAX_FRAME_SIZE}`,
    );
  }
  const out = Buffer.allocUnsafe(HEADER_SIZE + body.length);
  out.writeUInt32BE(body.length, 0);
  body.copy(out, HEADER_SIZE);
  return out;
}

/** 增量帧解码器。 */
export class FrameDecoder {
  private buf: Buffer = Buffer.alloc(0);

  /**
   * 喂入任意字节切片，返回其中完整解析出的帧。
   * 遇到协议违例抛 ProtoError；此后解码器状态不可信，应当断链。
   */
  push(chunk: Buffer): Frame[] {
    this.buf = this.buf.length === 0 ? chunk : Buffer.concat([this.buf, chunk]);
    const frames: Frame[] = [];
    while (this.buf.length >= HEADER_SIZE) {
      const n = this.buf.readUInt32BE(0);
      if (n === 0) {
        throw new ProtoError("malformed_frame", "zero-length frame");
      }
      if (n > MAX_FRAME_SIZE) {
        throw new ProtoError(
          "malformed_frame",
          `frame of ${n} bytes exceeds limit ${MAX_FRAME_SIZE}`,
        );
      }
      if (this.buf.length < HEADER_SIZE + n) {
        break; // 等待更多字节
      }
      const body = this.buf.subarray(HEADER_SIZE, HEADER_SIZE + n);
      this.buf = this.buf.subarray(HEADER_SIZE + n);
      frames.push(decodeBody(body));
    }
    return frames;
  }
}

function decodeBody(body: Buffer): Frame {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body.toString("utf8"));
  } catch {
    throw new ProtoError("malformed_frame", "frame body is not valid JSON");
  }
  const f = parsed as Partial<Frame>;
  if (f.v !== PROTOCOL_VERSION) {
    throw new ProtoError(
      "unsupported",
      `protocol version ${f.v}, want ${PROTOCOL_VERSION}`,
    );
  }
  if (!f.id || !f.type) {
    throw new ProtoError("malformed_frame", "frame missing id or type");
  }
  return f as Frame;
}

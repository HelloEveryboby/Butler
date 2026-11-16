package proto

import (
	"encoding/binary"
	"fmt"
	"io"
)

// TLV is the data-plane framing used for high-volume binary payloads
// (audio buffers, document bytes) that would be wasteful to base64-encode
// into JSON control frames. Wire layout (network byte order):
//
//	+--------+--------+----------------+
//	| tag:16 | len:32 | value: len ... |
//	+--------+--------+----------------+
//
// The control plane stays JSON (debuggable, replayable); the data plane is
// TLV (zero-copy friendly). Both travel over the same stream only when a
// dedicated data channel is not configured — production deployments should
// prefer splitting them to avoid head-of-line blocking.
type TLV struct {
	Tag   uint16
	Value []byte
}

// TLV header sizes.
const (
	tlvTagSize = 2
	tlvLenSize = 4
	tlvHdrSize = tlvTagSize + tlvLenSize
)

// MaxTLVValue bounds a single TLV value (256 MiB). Larger payloads must be
// split into multiple TLVs by the producer.
const MaxTLVValue = 256 << 20

// Well-known TLV tags for Butler's existing hybrid-link payloads.
const (
	TagAudioPCM   uint16 = 0x0001 // raw PCM frames from the C++ audio driver
	TagFFTSpectrum uint16 = 0x0002 // FFT output from the C++ DSP chain
	TagDocBlob    uint16 = 0x0003 // document/PDF byte blobs
	TagBinaryAck  uint16 = 0x000F // generic acknowledgement
	TagVendorMin  uint16 = 0x8000 // vendor/experiment range start
)

// MarshalBinary encodes the TLV, including its header.
func (t TLV) MarshalBinary() ([]byte, error) {
	if len(t.Value) > MaxTLVValue {
		return nil, fmt.Errorf("proto: TLV value of %d bytes exceeds limit %d", len(t.Value), MaxTLVValue)
	}
	out := make([]byte, tlvHdrSize+len(t.Value))
	binary.BigEndian.PutUint16(out[0:2], t.Tag)
	binary.BigEndian.PutUint32(out[2:6], uint32(len(t.Value)))
	copy(out[tlvHdrSize:], t.Value)
	return out, nil
}

// WriteTLV writes one TLV to w in a single write where possible.
func WriteTLV(w io.Writer, t TLV) error {
	buf, err := t.MarshalBinary()
	if err != nil {
		return err
	}
	if _, err := w.Write(buf); err != nil {
		return fmt.Errorf("proto: write TLV: %w", err)
	}
	return nil
}

// ReadTLV reads exactly one TLV from r.
func ReadTLV(r io.Reader) (TLV, error) {
	var hdr [tlvHdrSize]byte
	if _, err := io.ReadFull(r, hdr[:]); err != nil {
		return TLV{}, err
	}
	tag := binary.BigEndian.Uint16(hdr[0:2])
	n := binary.BigEndian.Uint32(hdr[2:6])
	if n > MaxTLVValue {
		return TLV{}, fmt.Errorf("proto: TLV value of %d bytes exceeds limit %d", n, MaxTLVValue)
	}
	val := make([]byte, n)
	if _, err := io.ReadFull(r, val); err != nil {
		return TLV{}, fmt.Errorf("proto: truncated TLV value: %w", err)
	}
	return TLV{Tag: tag, Value: val}, nil
}

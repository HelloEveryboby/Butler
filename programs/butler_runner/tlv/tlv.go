package tlv

import (
	"encoding/binary"
	"fmt"
	"io"
)

// TLV Frame Structure: [Type: 1B] [Length: 4B, Big-Endian] [Value: NB]

type Frame struct {
	Type  uint8
	Value []byte
}

func WriteFrame(w io.Writer, t uint8, v []byte) error {
	// Write Type
	if err := binary.Write(w, binary.BigEndian, t); err != nil {
		return err
	}
	// Write Length
	l := uint32(len(v))
	if err := binary.Write(w, binary.BigEndian, l); err != nil {
		return err
	}
	// Write Value
	_, err := w.Write(v)
	return err
}

func ReadFrame(r io.Reader) (*Frame, error) {
	var t uint8
	if err := binary.Read(r, binary.BigEndian, &t); err != nil {
		return nil, err
	}

	var l uint32
	if err := binary.Read(r, binary.BigEndian, &l); err != nil {
		return nil, err
	}

	v := make([]byte, l)
	if _, err := io.ReadFull(r, v); err != nil {
		return nil, err
	}

	return &Frame{Type: t, Value: v}, nil
}

func (f *Frame) String() string {
	return fmt.Sprintf("TLV[T:%d, L:%d]", f.Type, len(f.Value))
}

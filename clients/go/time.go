package oabp

import (
	"bytes"
	"strconv"
	"time"
)

// UnixTime is a time.Time that marshals to and from a JSON number of Unix
// seconds, matching the protocol's representation of fields like "deadline".
//
// It also tolerates a JSON string containing the seconds (some serializers emit
// large integers as strings) and a JSON null, which decodes to the zero value.
type UnixTime struct {
	t time.Time
}

// NewUnixTime wraps a time.Time.
func NewUnixTime(t time.Time) UnixTime { return UnixTime{t: t} }

// Time returns the underlying time.Time in UTC.
func (u UnixTime) Time() time.Time { return u.t.UTC() }

// Unix returns the value as Unix seconds. The zero value returns 0.
func (u UnixTime) Unix() int64 {
	if u.t.IsZero() {
		return 0
	}
	return u.t.Unix()
}

// IsZero reports whether the value is the zero time.
func (u UnixTime) IsZero() bool { return u.t.IsZero() }

// String renders the time in RFC3339 (UTC), or "0" when zero.
func (u UnixTime) String() string {
	if u.t.IsZero() {
		return "0"
	}
	return u.t.UTC().Format(time.RFC3339)
}

// MarshalJSON encodes the value as a JSON number of Unix seconds.
func (u UnixTime) MarshalJSON() ([]byte, error) {
	return []byte(strconv.FormatInt(u.Unix(), 10)), nil
}

// UnmarshalJSON decodes a JSON number (or numeric string, or null) of Unix
// seconds.
func (u *UnixTime) UnmarshalJSON(data []byte) error {
	data = bytes.TrimSpace(data)
	if len(data) == 0 || string(data) == "null" {
		u.t = time.Time{}
		return nil
	}
	// Accept a quoted numeric string by stripping surrounding quotes.
	if len(data) >= 2 && data[0] == '"' && data[len(data)-1] == '"' {
		data = data[1 : len(data)-1]
	}
	if len(data) == 0 {
		u.t = time.Time{}
		return nil
	}
	// Support fractional seconds (e.g. 1700000000.5) without losing the
	// fraction, while keeping the common integer path allocation-free.
	if sec, err := strconv.ParseInt(string(data), 10, 64); err == nil {
		u.t = time.Unix(sec, 0).UTC()
		return nil
	}
	f, err := strconv.ParseFloat(string(data), 64)
	if err != nil {
		return err
	}
	whole := int64(f)
	nsec := int64((f - float64(whole)) * 1e9)
	u.t = time.Unix(whole, nsec).UTC()
	return nil
}

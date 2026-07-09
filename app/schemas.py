"""Helpers for parsing input datetimes and rendering UTC responses."""
from datetime import datetime, timezone


def parse_input_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime into a naive UTC datetime for storage.

    Inputs that carry a UTC offset are normalized to UTC; naive inputs are
    treated as UTC as-is.
    """
    # Pydantic বা ইনপুট থেকে আসা স্ট্রিং/অবজেক্টকে হ্যান্ডেল করার জন্য সেফটি চেক
    if isinstance(value, datetime):
        dt = value
    else:
        # শেষে 'Z' থাকলে পাইথনের fromisoformat-এর সুবিধার জন্য '+00:00' বানিয়ে নেওয়া হচ্ছে
        if isinstance(value, str) and value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        
    if dt.tzinfo is not None:
        # BUG FIX 1 (Hard): প্রথমে সঠিক টাইমজোন অনুযায়ী UTC-তে কনভার্ট করা হচ্ছে (astimezone),
        # তারপর ডেটাবেসে naive হিসেবে সেভ করার জন্য tzinfo স্ট্রিপ করা হচ্ছে।
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt: datetime) -> str:
    """Render a stored (naive UTC) datetime with an explicit UTC designator."""
    if dt is None:
        return ""
    
    # ডেটাবেস থেকে পাওয়া naive ডেটটাইমকে প্রথমে UTC লোকাল করা হচ্ছে
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
        
    # BUG FIX 2 (Medium): পাইথনের ডিফল্ট '+00:00' কে হ্যাকাথনের কন্ট্রাক্ট অনুযায়ী
    # এক্সপ্লিসিট UTC ডিজাইনাতোর 'Z' দিয়ে রিপ্লেস করা হচ্ছে।
    res = dt.isoformat()
    if res.endswith("+00:00"):
        res = res[:-6] + "Z"
    elif not res.endswith("Z"):
        res = res + "Z"
        
    return res

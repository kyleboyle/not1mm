import datetime

def time_ago(utc_time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.datetime.now(datetime.UTC)
    if isinstance(utc_time, str):
        diff = now - datetime.datetime.strptime(utc_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.UTC)
    elif type(utc_time) is int:
        diff = now - datetime.datetime.fromtimestamp(utc_time, datetime.UTC)
    elif isinstance(utc_time, datetime.datetime):
        diff = now - utc_time
    elif not utc_time:
        diff = now - now
    else:
        raise ValueError('invalid date %s of type %s' % (utc_time, type(utc_time)))
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "5s"
        if second_diff < 60:
            return str(second_diff - second_diff % 10) + "s"
        if second_diff < 3600:
            return str(round(second_diff / 60)) + "m"
        if second_diff < 86400:
            return str( round(second_diff / 3600) ) + " hours ago"
    if day_diff == 1:
        return "1d"
    if day_diff < 7:
        return str(day_diff) + "d"
    if day_diff < 31:
        return str(round(day_diff/7)) + "w"
    if day_diff < 365:
        return str(round(day_diff/30)) + "months"
    return str(round(day_diff/365)) + "years"

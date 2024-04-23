"""http://wwrof.org/cabrillo/cabrillo-specification-v3/"""

from .cabrillo import CabrilloWriter

def convert_to_freq_field(freq_hz: int):
    freq_kz = int(freq_hz / 1000)
    freq_mz = freq_hz / 1_000_000
    if 1.8 <= freq_mz <= 29.7:
        return freq_kz
    elif 50 <= freq_mz <= 54:
        return '50'
    elif 70 <= freq_mz <= 71:
        return '70'
    elif 144 <= freq_mz <= 148:
        return '144'
    elif 222 <= freq_mz <= 225:
        return '222'
    elif 420 <= freq_mz <= 450:
        return '432'
    elif 902 <= freq_mz <= 928:
        return '902'
    elif 1240 <= freq_mz <= 1300:
        return '1.2G'
    elif 2300 <= freq_mz <= 2450:
        return '2.3G'
    elif 3300 <= freq_mz <= 3500:
        return '3.4G'
    elif 5650 <= freq_mz <= 5925:
        return '5.7G'
    elif 10000 <= freq_mz <= 10500:
        return '10G'
    elif 24000 <= freq_mz <= 24250:
        return '24G'
    elif 47000 <= freq_mz <= 47200:
        return '47G'
    elif 75500 <= freq_mz <= 81000:
        return '75G'
    elif 119980 <= freq_mz <= 120020:
        return '122G'
    elif 142000 <= freq_mz <= 149000:
        return '134G'
    elif 241000 <= freq_mz <= 250000:
        return '241G'
    elif 300000 <= freq_mz <= 7500000:
        return 'LIGHT'
    return None
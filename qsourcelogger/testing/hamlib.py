import serial.tools.list_ports

from qsourcelogger.cat.libhamlib import Hamlib
import sys

STATUS_CODES = {0: 'Alpha', 1: 'Untested', 2: 'Beta', 3: 'Stable', '': ''}

def rot_get_models():
    """
    Return a list of all Hamlib rotator models
    :rtype: list of dict
    """
    Hamlib.rot_load_all_backends()
    models = []
    for macro_name in dir(Hamlib):
        if not macro_name.startswith('ROT_MODEL'):
            continue

        model_id = getattr(Hamlib, macro_name)

        model = {'id': model_id, 'macro_name': macro_name}

        # Try to get more information via Rotator Capabilities
        rot_caps = Hamlib.rot_get_caps(model_id)

        for key in ['mfg_name', 'model_name', 'version', 'status']:
            try:
                model[key] = getattr(rot_caps, key)
            except AttributeError:
                model[key] = ''

        models.append(model)

    return models


def rig_get_models():
    """
    Return a list of all Hamlib rotator models
    :rtype: list of dict
    """
    Hamlib.rig_load_all_backends()
    models = []
    for macro_name in dir(Hamlib):
        if not macro_name.startswith('RIG_MODEL'):
            continue

        model_id = getattr(Hamlib, macro_name)

        model = {'id': model_id, 'macro_name': macro_name}

        rig_caps = Hamlib.rig_get_caps(model_id)

        for key in ['mfg_name', 'model_name', 'version', 'status']:
            try:
                model[key] = getattr(rig_caps, key)
            except AttributeError:
                model[key] = ''

        models.append(model)

    return models

def rot_print_models_table(models):
    """
    Print all rotator models from the provided list.
    :param: Input list of rotator models
    """
    print(f'|{"Rot #":6s} '
          f'| {"Manufacturer":12s} '
          f'| {"Model":21s} '
          f'| {"Version":11s} '
          f'| {"Status":8s} '
          f'| {"Macro Name":28s} |')
    print('|-------'
          '|--------------'
          '|-----------------------'
          '|-------------'
          '|----------'
          '|------------------------------|')
    for model in sorted(models, key=lambda m: m['id']):
        print('| '
              f'{model["id"]:5d} | '
              f'{model["mfg_name"]:12s} | '
              f'{model["model_name"]:21s} | '
              f'{model["version"]:11s} | '
              f'{STATUS_CODES[model["status"]]:8s} | '
              f'{model["macro_name"]:28s} |')

def StartUp():
    """Simple script to test the Hamlib.py module with Python3."""

    print("%s: Python %s; %s\n" \
          % (sys.argv[0], sys.version.split()[0], Hamlib.cvar.hamlib_version))

    Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)

    # Init RIG_MODEL_DUMMY
    my_rig = Hamlib.Rig(Hamlib.RIG_MODEL_DUMMY)
    my_rig.set_conf("rig_pathname", "/dev/Rig")
    my_rig.set_conf("retry", "5")
    my_rig.open()

    rpath = my_rig.get_conf("rig_pathname")
    retry = my_rig.get_conf("retry")

    print("status(str):\t\t%s" % Hamlib.rigerror(my_rig.error_status))
    print("get_conf:\t\tpath = %s, retry = %s" \
          % (rpath, retry))

    my_rig.set_freq(Hamlib.RIG_VFO_B, 5700000000)
    my_rig.set_vfo(Hamlib.RIG_VFO_B)

    print("freq:\t\t\t%s" % my_rig.get_freq())

    my_rig.set_freq(Hamlib.RIG_VFO_A, 145550000)
    (mode, width) = my_rig.get_mode(Hamlib.RIG_VFO_A)

    print("mode:\t\t\t%s\nbandwidth:\t\t%s" % (Hamlib.rig_strrmode(mode), width))

    my_rig.set_mode(Hamlib.RIG_MODE_CW)
    (mode, width) = my_rig.get_mode()

    print("mode:\t\t\t%s\nbandwidth:\t\t%s" % (Hamlib.rig_strrmode(mode), width))

    print("Backend copyright:\t%s" % my_rig.caps.copyright)
    print("Model:\t\t\t%s" % my_rig.caps.model_name)
    print("Manufacturer:\t\t%s" % my_rig.caps.mfg_name)
    print("Backend version:\t%s" % my_rig.caps.version)
    print("Backend status:\t\t%s" % Hamlib.rig_strstatus(my_rig.caps.status))
    print("Rig info:\t\t%s" % my_rig.get_info())

    my_rig.set_level("VOXDELAY",  1)

    print("VOX delay:\t\t%s" % my_rig.get_level_i("VOXDELAY"))

    my_rig.set_level(Hamlib.RIG_LEVEL_VOXDELAY, 5)

    print("VOX delay:\t\t%s" % my_rig.get_level_i(Hamlib.RIG_LEVEL_RFPOWER))

    af = 12.34

    print("Setting AF to %0.2f...." % (af))

    my_rig.set_level("AF", af)

    print("status:\t\t\t%s - %s" % (my_rig.error_status,
                                    Hamlib.rigerror(my_rig.error_status)))

    print("AF level:\t\t%0.2f" % my_rig.get_level_f(Hamlib.RIG_LEVEL_AF))
    print("strength:\t\t%s" % my_rig.get_level_i(Hamlib.RIG_LEVEL_STRENGTH))
    print("status:\t\t\t%s" % my_rig.error_status)
    print("status(str):\t\t%s" % Hamlib.rigerror(my_rig.error_status))

    chan = Hamlib.channel(Hamlib.RIG_VFO_B)
    my_rig.get_channel(chan,1)

    print("get_channel status:\t%s" % my_rig.error_status)
    print("VFO:\t\t\t%s, %s" % (Hamlib.rig_strvfo(chan.vfo), chan.freq))
    print("Attenuators:\t\t%s" % my_rig.caps.attenuator)
    # Can't seem to get get_vfo_info to work
    #(freq, width, mode, split) = my_rig.get_vfo_info(Hamlib.RIG_VFO_A,freq,width,mode,split)
    #print("Rig vfo_info:\t\tfreq=%s, mode=%s, width=%s, split=%s" % (freq, mode, width, split))
    print("\nSending Morse, '73'")

    my_rig.send_morse(Hamlib.RIG_VFO_A, "73")
    my_rig.close()

    print("\nSome static functions:")

    err, lon1, lat1 = Hamlib.locator2longlat("IN98XC")
    err, lon2, lat2 = Hamlib.locator2longlat("DM33DX")
    err, loc1 = Hamlib.longlat2locator(lon1, lat1, 3)
    err, loc2 = Hamlib.longlat2locator(lon2, lat2, 3)

    print("Loc1:\t\tIN98XC -> %9.4f, %9.4f -> %s" % (lon1, lat1, loc1))
    print("Loc2:\t\tDM33DX -> %9.4f, %9.4f -> %s" % (lon2, lat2, loc2))

    err, dist, az = Hamlib.qrb(lon1, lat1, lon2, lat2)
    longpath = Hamlib.distance_long_path(dist)

    print("Distance:\t%.3f km, azimuth %.2f, long path:\t%.3f km" \
          % (dist, az, longpath))

    # dec2dms expects values from 180 to -180
    # sw is 1 when deg is negative (west or south) as 0 cannot be signed
    err, deg1, mins1, sec1, sw1 = Hamlib.dec2dms(lon1)
    err, deg2, mins2, sec2, sw2 = Hamlib.dec2dms(lat1)

    lon3 = Hamlib.dms2dec(deg1, mins1, sec1, sw1)
    lat3 = Hamlib.dms2dec(deg2, mins2, sec2, sw2)

    print('Longitude:\t%4.4f, %4d° %2d\' %2d" %1s\trecoded: %9.4f' \
        % (lon1, deg1, mins1, sec1, ('W' if sw1 else 'E'), lon3))

    print('Latitude:\t%4.4f, %4d° %2d\' %2d" %1s\trecoded: %9.4f' \
        % (lat1, deg2, mins2, sec2, ('S' if sw2 else 'N'), lat3))

    my_rig.set_vfo_opt(0);

if __name__ == '__main__':
    StartUp()
    models = rot_get_models()
    rot_print_models_table(models)

    models = rig_get_models()
    rot_print_models_table(models)



    #list = serial.tools.list_ports.comports()
    #for i in list:
    #    print(i.device)
    from qsourcelogger.cat.hamlib import CatHamlib
    cat = CatHamlib('RIG_MODEL_FT710', '/dev/cu.JabraEvolve75', '322323')
    cat.connect()
    cat.get_state()


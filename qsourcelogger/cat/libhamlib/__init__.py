import logging
# sys.platform = darwin   linux
# platform.mahcine() = aarch64, arm64

# macos build
# ./configure --with-python-binding --prefix=$HOME/local PYTHON=$(which python3.11) LIBUSB_LIBS="/opt/homebrew/Cellar/libusb/1.0.27/lib/libusb-1.0.a" --without-cxx-binding CFLAGS=$(pkg-config --cflags libusb-1.0) LDFLAGS="$(pkg-config --libs libusb-1.0)"

# darwin arm64
# linux aarch64
import sys, platform

logger = logging.getLogger(__name__)

plat = f"{sys.platform}-{platform.machine()}".lower()
mode_int_to_token = {}

try:
    # give env install a chance to load first
    import Hamlib as Hamlib
except:
    try:
        # load bundled module
        from . import Hamlib as Hamlib
    except Exception as e:
        Hamlib = None
        logger.warning(f"Hamlib not available {e}")

if Hamlib:
    Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
    for macro in filter(lambda x: x.startswith("RIG_MODE_"), dir(Hamlib)):
        mode_int_to_token[getattr(Hamlib, macro)] = macro[9:]

def mode_to_token(mode):
    return mode_int_to_token.get(mode, '')

def rig_get_models():
    Hamlib.rig_load_all_backends()
    models = []
    for macro_name in dir(Hamlib):
        if not macro_name.startswith('RIG_MODEL'):
            continue

        model_id = getattr(Hamlib, macro_name)

        model = {'id': model_id, 'macro_name': macro_name, 'macro': getattr(Hamlib, macro_name)}

        rig_caps = Hamlib.rig_get_caps(model_id)

        for key in ['mfg_name', 'model_name', 'version', 'status']:
            try:
                model[key] = getattr(rig_caps, key)
            except AttributeError:
                model[key] = ''

        models.append(model)

    return models



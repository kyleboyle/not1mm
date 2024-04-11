from peewee import Model, CharField, IntegerField, ForeignKeyField, TextField, DateTimeField, FloatField, DoubleField, \
    UUIDField, BooleanField
from playhouse.sqlite_ext import SqliteExtDatabase, JSONField
from . import persistent_migrations
_database = SqliteExtDatabase(None)

class BaseModel(Model):
    class Meta:
        database = _database


class Station(BaseModel):
    station_name = CharField()
    callsign = CharField(20)
    arrl_sect = CharField(20, null=True)

    club = CharField(null=True)
    email = CharField(null=True)
    antenna = CharField(null=True)
    rig = CharField(null=True)

    gridsquare = CharField(20, null=True)
    gridsquare_ext = CharField(20, null=True)
    latitude = DoubleField(null=True)
    longitude = DoubleField(null=True)
    altitude = DoubleField(null=True)
    cq_zone = IntegerField(null=True)
    dxcc = IntegerField(null=True)
    iaru_zone = IntegerField(null=True)
    itu_zone = IntegerField(null=True)

    license_class = CharField(20, null=True)
    name = CharField(null=True)
    street1 = CharField(null=True)
    street2 = CharField(null=True)
    city = CharField(null=True)
    state = CharField(null=True)
    postal_code = CharField(20, null=True)
    county = CharField(null=True)
    country = CharField(null=True)
    continent = CharField(2, null=True)  # NA,SA,EU,AF,OC,AS,AN

    iota = CharField(null=True)
    iota_island_id = CharField(null=True)
    pota_ref = CharField(null=True)
    fists = IntegerField(null=True)
    usaca_counties = CharField(null=True)
    vucc_grids = CharField(null=True)
    wwff_ref = CharField(null=True)
    sota_ref = CharField(null=True)
    sig = CharField(null=True)
    sig_info = CharField(null=True)

    deleted = BooleanField(default=False, null=True)
    #packet_node = CharField(null=True)
    #rover_qth = CharField(null=True)
    #antenna1 = CharField(30)
    #antenna2 = CharField(30)


class ContestMeta(BaseModel):
    name = CharField(30, null=True, primary_key=True)
    display_name = CharField()
    sort_order = IntegerField(null=True)
    period = IntegerField(null=True)
    points_per_contact = IntegerField(null=True)
    mode = CharField(10)
    dupe_type = IntegerField()
    cabrillo_name = CharField(20)
    cabrillo_version = CharField(20)
    multiplier1_name = CharField(20, null=True)
    multiplier2_name = CharField(20, null=True)
    multiplier3_name = CharField(20, null=True)
    digi_messages = CharField(null=True)
    cw_messages = CharField(null=True)
    master_dta = CharField(null=True)
    ssb_messages = CharField(null=True)


class Contest(BaseModel):
    fk_contest_meta = ForeignKeyField(ContestMeta)
    start_date = DateTimeField()
    deleted = CharField(default=False)
    fk_station = ForeignKeyField(Station)
    assisted_category = CharField(30, null=True)
    band_category = CharField(30, null=True)
    claimed_score = IntegerField(null=True)
    mode_category = CharField(30, null=True)
    operator_category = CharField(30, null=True)
    operators = CharField(null=True)
    overlay_category = CharField(20, null=True)
    power_category = CharField(20, null=True)
    sent_exchange = CharField(50, null=True)
    soapbox = TextField(null=True)
    station_category = CharField(30, null=True)
    sub_type = CharField(20, null=True)
    time_category = CharField(30, null=True)
    transmitter_category = CharField(30, null=True)

# when creating a new record use .save(force_insert=True) because the id is not auto incrementing
class QsoLog(BaseModel):
    id = UUIDField(primary_key=True)
    time_on = DateTimeField(index=True)
    station_callsign = CharField(20, index=True)
    call = CharField(20, index=True)
    time_off = DateTimeField(null=True)
    rst_sent = CharField(10)
    rst_rcvd = CharField(10)
    freq = IntegerField()
    freq_rx = IntegerField(null=True) # if running split
    band = CharField(10) # https://www.adif.org/314/ADIF_314.htm#Band_Enumeration
    mode = CharField(20) # https://www.adif.org/314/ADIF_314.htm#Mode_Enumeration
    submode = CharField(20, null=True) # https://www.adif.org/314/ADIF_314.htm#Submode_Enumeration
    name = CharField(null=True)
    comment = CharField(null=True)
    stx = IntegerField(null=True) # serial number transmitted
    stx_string = CharField(null=True) # transmitted contest contents (if contest specific fields don't cover it)
    srx = IntegerField(null=True)
    srx_string = CharField(null=True)
    gridsquare = CharField(20, null=True)
    gridsquare_ext = CharField(20, null=True)
    qth = CharField(null=True)
    county = CharField(20, null=True) # https://www.adif.org/314/ADIF_314.htm#Secondary_Administrative_Subdivision
    country = CharField(30, null=True) # DXCC entity name
    continent = CharField(2, null=True)  # NA,SA,EU,AF,OC,AS,AN
    state = CharField(20, null=True)
    ve_prov = CharField(20, null=True)
    dxcc = IntegerField(null=True)
    prefix = IntegerField(null=True) # region / dxcc prefix
    cqz = IntegerField(null=True)
    ituz = IntegerField(null=True)
    arrl_sect = CharField(4, null=True) # https://www.adif.org/314/ADIF_314.htm#ARRL_Section_Enumeration
    wpx_prefix = CharField(10, null=True)
    pota_ref = CharField(null=True) # pota ref csv list. eg K-0817,K-4566,K-4576,K-4573,K-4578@US-WY
    wwff_ref = CharField(20, null=True)
    iota = CharField(15, null=True) # CC-XXX
    sota_ref = CharField(20, null=True)  # a single summit ref, eg W2/WE-003   G/LD-003
    distance = IntegerField(null=True) # positive kilometers via the specified signal path
    tx_pwr = IntegerField(null=True)
    points = IntegerField(null=True) # points for qso in a contest
    a_index = IntegerField(null=True) # the geomagnetic A index at the time of the QSO in the range 0 to 400 (inclusive)
    address = CharField(null=True)
    age = IntegerField(null=True)
    altitude = FloatField(null=True)
    ant_path = CharField(2, null=True) # G(grayline), O(other), S(short path), L(long path)
    award_granted = CharField(null=True)
    award_submitted = CharField(null=True)
    band_rx = CharField(null=True)
    check = CharField(null=True)
    class_lic = CharField(null=True)
    clublog_qso_upload_date = DateTimeField(null=True)
    clublog_qso_upload_status = CharField(null=True)
    contacted_op = CharField(null=True)
    contest_id = CharField(null=True)
    credit_granted = CharField(null=True)
    credit_submitted = CharField(null=True)
    darc_dok = CharField(10, null=True) # District Location Code
    email = CharField(null=True) #contacted stations' email
    eq_call = CharField(20, null=True) # the contacted station's owner's callsign
    eqsl_qsl_rcvd = CharField(2, null=True) # https://www.adif.org/314/ADIF_314.htm#QSLRcvd_Enumeration
    eqsl_qslrdate = DateTimeField(null=True)
    eqsl_qsl_sent = CharField(2, null=True)
    eqsl_qslsdate = DateTimeField(null=True)
    fists = IntegerField(null=True)
    fists_cc = IntegerField(null=True)
    force_init = BooleanField(null=True)
    guest_op = CharField(null=True)
    hamlogeu_qso_upload_date = DateTimeField(null=True)
    hamlogeu_qso_upload_status = CharField(2, null=True) # Y N M https://www.adif.org/314/ADIF_314.htm#QSOUploadStatus_Enumeration
    hamqth_qso_upload_date = DateTimeField(null=True)
    hamqth_qso_upload_status = CharField(2, null=True)
    hrdlog_qso_upload_date = DateTimeField(null=True)
    hrdlog_qso_upload_status = CharField(2, null=True)
    iota_island_id = IntegerField(null=True)
    k_index = IntegerField(null=True) # the geomagnetic K index at the time of the QSO [0, 9]
    lat = CharField(20, null=True) # XDDD MM.MMM
    lon = CharField(20, null=True) # XDDD MM.MMM
    lotw_qsl_rcvd = CharField(2, null=True) # https://www.adif.org/314/ADIF_314.htm#QSLRcvd_Enumeration
    lotw_qsl_sent = CharField(2, null=True)
    lotw_qslrdate = DateTimeField(null=True)
    lotw_qslsdate = DateTimeField(null=True)
    max_bursts = IntegerField(null=True)
    ms_shower = CharField(null=True) # the name of the meteor shower in progress
    my_altitude = FloatField(null=True) # meters
    my_antenna = CharField(null=True)
    my_ant_az = IntegerField(null=True)
    my_ant_el = IntegerField(null=True)
    my_arrl_sect = CharField(4, null=True)
    my_city = CharField(null=True)
    my_county = CharField(20, null=True)
    my_country = CharField(20, null=True)
    my_cq_zone = IntegerField(null=True)
    my_dxcc = IntegerField(null=True)
    my_fists = IntegerField(null=True)
    my_gridsquare = CharField(8, null=True) # max 8 length
    my_gridsquare_ext = CharField(2, null=True) # if there is a 10 character gridsquare, this is the final 2 characters
    my_iota = CharField(15, null=True) # CC-XXX
    my_iota_island_id = IntegerField(null=True)
    my_itu_zone = IntegerField(null=True)
    my_lat = CharField(20, null=True) # XDDD MM.MMM
    my_lon = CharField(20, null=True) # XDDD MM.MMM
    my_name = CharField(null=True)
    my_postal_code = CharField(20, null=True)
    my_pota_ref = CharField(null=True) # pota ref csv list. eg K-0817,K-4566,K-4576,K-4573,K-4578@US-WY
    my_rig = CharField(null=True)
    my_sig = CharField(null=True)
    my_sig_info = CharField(null=True)
    my_sota_ref = CharField(20, null=True)
    my_state = CharField(10, null=True)
    my_street = CharField(null=True)
    my_usaca_counties = CharField(null=True)
    my_vucc_grids = CharField(null=True)
    my_wwff_ref = CharField(null=True)
    notes = TextField(null=True)
    nr_bursts = IntegerField(null=True)
    nr_pings = IntegerField(null=True)
    operator = CharField(20, null=True)
    owner_callsign = CharField(20, null=True)
    precedence = CharField(10, null=True)
    prop_mode = CharField(15, null=True)
    public_key = CharField(null=True)
    qrzcom_qso_upload_date = DateTimeField(null=True)
    qrzcom_qso_upload_status = CharField(2, null=True) # Y N M
    qsl_rcvd = CharField(2, null=True)
    qsl_rcvd_via = CharField(2, null=True)
    qsl_sent = CharField(2, null=True)
    qsl_sent_via = CharField(2, null=True)
    qsl_via = CharField(null=True)
    qslmsg = TextField(null=True)
    qslrdate = DateTimeField(null=True)
    qslsdate = DateTimeField(null=True)
    qso_complete = CharField(4, null=True) # Y yes, N no, NIL not heard, ? uncertain
    qso_random = BooleanField(null=True)
    region = CharField(5, null=True) #the contacted station's WAE or CQ entity contained within a DXCC entity.
    rig = TextField(null=True)
    rx_pwr = IntegerField(null=True) # the contacted station's transmitter power in Watts
    sat_mode = CharField(null=True)
    sat_name = CharField(null=True)
    sfi = IntegerField(null=True)
    sig = CharField(null=True)
    sig_info = CharField(null=True)
    silent_key = BooleanField(null=True)
    skcc = CharField(null=True) # the contacted station's Straight Key Century Club (SKCC) member information
    swl = BooleanField(null=True)
    ten_ten = IntegerField(null=True)
    uksmg = IntegerField(null=True)
    usaca_counties = CharField(null=True)
    vucc_grids = CharField(null=True)
    web = CharField(null=True)
    other = JSONField(null=True) # catch-all json document
    is_original = BooleanField(null=True) # log generated while using this app
    is_run = BooleanField(null=True) # contest operator is in 'run' mode (calling cq)
    fk_station = ForeignKeyField(Station)
    fk_contest = ForeignKeyField(Contest)
    #fk_rig = ForeignKeyField(R)


class DeletedQsoLog(QsoLog):
    pass



def loadPersistantDb(path: str):
    _database.init(path, pragmas=(
        ('check_same_thread', False),
        ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
        ('foreign_keys', 1)))  # Enforce foreign-key constraints.
    _database.create_tables([Station, Contest, ContestMeta, QsoLog, DeletedQsoLog])

    for migration in persistent_migrations.funcs:
        migration(_database)

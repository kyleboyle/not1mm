"""
bigcty.py - part of miaowware/ctyparser
---

Copyright 2019-2022 classabbyamp, 0x5c
Released under the terms of the MIT license.
"""
import collections
import csv
import json
import os
import pathlib
import re
import tempfile
import zipfile
from datetime import datetime
from typing import Union

import feedparser
import requests

default_feed = "http://www.country-files.com/category/big-cty/feed/"


class BigCty(collections.abc.Mapping):
    """Class representing a BigCTY dataset. utilizing static data set so multiple instances do not duplicate memory.
    Can be initialised with data by passing the path to a valid ``cty.json`` file to the constructor.

    :param file_path: Location of the ``cty.json`` file to load.
    :type file_path: str or os.PathLike, optional

    :var version: the datestamp of the data, ``YYYYMMDD`` format.
    :vartype version: str
    """
    regex_version_entry = re.compile(r"VER(\d{8})")
    regex_feed_date = re.compile(r'(\d{2}-\w+-\d{4})')
    regex_dat = re.compile(r"""=?(?P<prefix>[a-zA-Z0-9/]+)
                                 (?:\((?P<cq>\d+)\))?
                                 (?:\[(?P<itu>\d+)\])?
                                 (?P<latlong>
                                     <(?P<lat>[+-]?\d+(?:\.\d+)?)
                                     \/
                                     (?P<long>[+-]?\d+(?:.\d+)?)>
                                 )?
                                 (?:\{(?P<continent>\w+)\})?
                                 (?:~(?P<tz>[+-]?\d+(?:\.\d+)?)~)?""", re.X)

    _data: dict = {}
    _version = ""
    def __init__(self, file_path: Union[str, os.PathLike, None] = None):

        if file_path is not None and not self._data:
            self.load(file_path)

    def load(self, cty_file: Union[str, os.PathLike]) -> None:
        """Loads a ``cty.json`` file into the instance.

        :param cty_file: Path to the file to load.
        :type cty_file: str or os.PathLike
        :return: None
        """
        cty_file = pathlib.Path(cty_file)
        with cty_file.open("r") as file:
            ctyjson = json.load(file)
            type(self)._version = ctyjson.pop("version", None)
            type(self)._data = ctyjson

    def dump(self, cty_file: Union[str, os.PathLike]) -> None:
        """Dumps the data of the instance to a ``cty.json`` file.

        :param cty_file: Path to the file to dump to.
        :type cty_file: str or os.PathLike
        :return: None
        """
        cty_file = pathlib.Path(cty_file)
        datadump = type(self)._data.copy()
        datadump["version"] = type(self)._version
        with cty_file.open("w") as file:
            json.dump(datadump, file)

    def import_csv(self, csv_file: Union[str, os.PathLike]) -> None:
        """Imports CTY data from a ``CTY.CSV`` file.

        :param dat_file: Path to the file to import.
        :type dat_file: str or os.PathLike
        :return: None
        """
        dat_file = pathlib.Path(csv_file)
        with dat_file.open("r") as file:
            cty_dict = dict()

            # get the version from the file
            csvreader = csv.reader(file)
            for line in csvreader:
                primary = line[0]
                entity = {
                    'entity': line[1], 'dxcc': line[2], 'cq': int(line[4]),
                    'itu': int(line[5]), 'continent': line[3],
                    'lat': float(line[6]), 'long': float(line[7]),
                    'tz': -1 * float(line[8]), 'len': len(line[0]),
                    'exact_match': False
                }
                if primary.startswith('*'):
                    # not a dxcc entity, make it a reference to
                    primary = primary[1:]
                    entity['dxcc_ref'] = entity['dxcc']
                    del entity['dxcc']
                entity['primary_pfx'] = primary
                cty_dict[primary] = dict(entity)
                for secondary in line[9][:-1].split(' '):
                    exact = False
                    if secondary.startswith('='):
                        secondary = secondary[1:]
                        exact = True
                    if secondary.startswith('VER') and self.regex_version_entry.match(secondary):
                        type(self)._version = secondary[3:]

                    if secondary not in cty_dict.keys():
                        secondary_entity = dict(entity)
                        secondary_entity['exact_match'] = exact
                        match = re.search(self.regex_dat, secondary)
                        if match is None:
                            continue
                        if match.group("itu"):
                            secondary_entity['itu'] = int(match.group("itu"))
                        if match.group("cq"):
                            secondary_entity['cq'] = int(match.group("cq"))
                        if match.group("latlong"):
                            secondary_entity['lat'] = float(match.group("lat"))
                            secondary_entity['long'] = float(match.group("long"))
                        if match.group("continent"):
                            secondary_entity['continent'] = match.group("continent")
                        if match.group("tz"):
                            secondary_entity['tz'] = -1 * float(match.group("tz"))
                        cty_dict[match.group("prefix")] = secondary_entity

        type(self)._data = cty_dict

    def update(self) -> bool:
        """Upates the instance's data from the feed.

        :raises Exception: If there is no date in the feed.
        :return: ``True`` if an update was done, otherwise ``False``.
        :rtype: bool
        """
        with requests.Session() as session:
            feed = session.get(default_feed)
            parsed_feed = feedparser.parse(feed.content)
            update_url = parsed_feed.entries[0]['link']
            date_match = re.search(self.regex_feed_date, update_url)
            if date_match is None:
                raise Exception("Error parsing feed: date missing")  # TODO: Better exception
            date_str = date_match.group(1).title()
            update_date = datetime.strftime(datetime.strptime(date_str, '%d-%B-%Y'), '%Y%m%d')

            if type(self)._version == update_date:
                return False

            with tempfile.TemporaryDirectory() as temp:
                path = pathlib.PurePath(temp)
                dl_url = f'http://www.country-files.com/bigcty/download/{update_date[:4]}/bigcty-{update_date}.zip'  # TODO: Issue #10
                rq = session.get(dl_url)
                if rq.status_code == 404:
                    dl_url = f'http://www.country-files.com/bigcty/download/bigcty-{update_date}.zip'
                    rq = session.get(dl_url)
                    if rq.status_code != 200:
                        raise Exception(f"Unable to find and download bigcty-{update_date}.zip")
                with open(path / 'cty.zip', 'wb+') as file:
                    file.write(rq.content)
                    zipfile.ZipFile(file).extract('cty.csv', path=str(path))  # Force cast as str because mypy
                self.import_csv(path / "cty.csv")
        return True

    @property
    def formatted_version(self) -> str:
        """Formatted representation of the version/date of the current BigCTY data.

        :getter: Returns version in ``YYYY-MM-DD`` format, or ``0000-00-00`` (if invalid date)
        :type: str
        """
        try:
            return datetime.strptime(type(self)._version, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return "0000-00-00"

    @property
    def version(self) -> str:
        """The version/date of the current BigCTY data.

        :getter: Returns version in ``YYYYMMDD`` format
        :type: str
        """
        return type(self)._version

    # --- Wrappers to implement dict-like functionality ---
    def __len__(self):
        return len(type(self)._data)

    def __getitem__(self, key: str):
        return type(self)._data[key]

    def __iter__(self):
        return iter(type(self)._data)

    # --- Standard methods we should all implement ---
    # str(): Simply return what it would be for the underlaying dict
    def __str__(self):
        return str(type(self)._data)

    # repr(): Class name, instance ID, and last_updated
    def __repr__(self):
        return (f'<{type(self).__module__}.{type(self).__qualname__} object'
                f'at {hex(id(self))}, version={type(self)._version}>')

    def find_call_match(self, call):
        callsign = call.upper()
        for count in reversed(range(len(callsign))):
            searchitem = callsign[: count + 1]
            result = type(self)._data.get(searchitem, None)
            if not result:
                continue
            if result.get("exact_match", None):
                if searchitem == callsign:
                    return result
                continue
            return result

if __name__ == "__main__":
    cty = BigCty()
    cty.update()
    cty.version
    #cty.dump()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module uses a PE file object to extract all the RT group icons
"""

__author__ = "Paolo Di Prodi"
__copyright__ = "Copyright 2017, LogstTotal Project"
__license__ = "Apache"
__version__ = "2.0"
__maintainer__ = "Paolo Di Prodi"
__email__ = "paolo@logstotal.com"
__status__ = "Experimental"


import io
import struct
import pefile
from PIL import Image

class ExtractIcon(object):
    GRPICONDIRENTRY_format = ('GRPICONDIRENTRY',
                              ('B,Width', 'B,Height', 'B,ColorCount', 'B,Reserved',
                               'H,Planes', 'H,BitCount', 'I,BytesInRes', 'H,ID'))
    GRPICONDIR_format = ('GRPICONDIR',
                         ('H,Reserved', 'H,Type', 'H,Count'))
    RES_ICON = 1
    RES_CURSOR = 2

    def __init__(self, pe):
        self.pe = pe

    def find_resource_base(self, types):
        try:

            rt_base_idx = [entry.id for
                           entry in self.pe.DIRECTORY_ENTRY_RESOURCE.entries].index(
                pefile.RESOURCE_TYPE[types]
            )
        except AttributeError:
            rt_base_idx = None
        except ValueError:
            rt_base_idx = None

        if rt_base_idx is not None:
            return self.pe.DIRECTORY_ENTRY_RESOURCE.entries[rt_base_idx]

        return None

    def find_resource(self, types, res_index):
        rt_base_dir = self.find_resource_base(types)

        if res_index < 0:
            try:
                idx = [entry.id for entry in rt_base_dir.directory.entries].index(-res_index)
            except:
                return None
        else:
            idx = res_index if res_index < len(rt_base_dir.directory.entries) else None

        if idx is None:
            return None

        test_res_dir = rt_base_dir.directory.entries[idx]
        res_dir = test_res_dir
        if test_res_dir.struct.DataIsDirectory:
            res_dir = test_res_dir.directory.entries[0]
        if res_dir.struct.DataIsDirectory:
            return None

        return res_dir

    def get_group_icons(self):
        rt_base_dir = self.find_resource_base('RT_GROUP_ICON')
        groups = []

        if not hasattr(rt_base_dir, "directory"):
            return groups

        for res_index in range(0, len(rt_base_dir.directory.entries)):
            grp_icon_dir_entry = self.find_resource('RT_GROUP_ICON', res_index)

            if not grp_icon_dir_entry:
                continue

            data_rva = grp_icon_dir_entry.data.struct.OffsetToData
            size = grp_icon_dir_entry.data.struct.Size
            data = self.pe.get_memory_mapped_image()[data_rva:data_rva + size]
            file_offset = self.pe.get_offset_from_rva(data_rva)

            grp_icon_dir = pefile.Structure(self.GRPICONDIR_format, file_offset=file_offset)
            grp_icon_dir.__unpack__(data)

            if grp_icon_dir.Reserved != 0 or grp_icon_dir.Type != self.RES_ICON:
                continue
            offset = grp_icon_dir.sizeof()

            entries = []
            for idx in range(0, grp_icon_dir.Count):
                grp_icon = pefile.Structure(self.GRPICONDIRENTRY_format, file_offset=file_offset + offset)
                grp_icon.__unpack__(data[offset:])
                offset += grp_icon.sizeof()
                entries.append(grp_icon)

            groups.append(entries)
        return groups

    def get_icon(self, index):
        icon_entry = self.find_resource('RT_ICON', -index)
        if not icon_entry:
            return None

        data_rva = icon_entry.data.struct.OffsetToData
        size = icon_entry.data.struct.Size
        data = self.pe.get_memory_mapped_image()[data_rva:data_rva + size]

        return data

    def export_raw(self, entries, index=None):
        if index is not None:
            entries = entries[index:index + 1]

        ico = struct.pack('<HHH', 0, self.RES_ICON, len(entries))
        data_offset = None
        data = []
        info = []
        for grp_icon in entries:
            if data_offset is None:
                data_offset = len(ico) + ((grp_icon.sizeof() + 2) * len(entries))

            nfo = grp_icon.__pack__()[:-2] + struct.pack('<L', data_offset)
            info.append(nfo)

            raw_data = self.get_icon(grp_icon.ID)
            if not raw_data:
                continue

            data.append(raw_data)
            data_offset += len(raw_data)

        return ico + b"".join(info) + b"".join(data)

    def export(self, entries, index=None):
        raw = self.export_raw(entries, index)
        try:
            img = Image.open(io.BytesIO(raw))
            return img
        except:
            return None

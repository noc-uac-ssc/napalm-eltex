"""
Napalm driver for Eltes switches.
"""
from __future__ import unicode_literals
import hashlib
import re
import socket
from io import StringIO

import napalm.base.constants as c
import pandas as pd
# import NAPALM Base
from napalm.base.base import NetworkDriver
from napalm.base.exceptions import (
    ConnectionException,
)
# import third party lib
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException

# from scp import SCPClient

# Easier to store these as constants
HOUR_SECONDS = 3600
DAY_SECONDS = 24 * HOUR_SECONDS
WEEK_SECONDS = 7 * DAY_SECONDS
YEAR_SECONDS = 365 * DAY_SECONDS


class CEDriver(NetworkDriver):
    """Napalm driver for Eltex switches."""

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        """NAPALM Eltex Handler."""
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout

        # Get optional arguments
        if optional_args is None:
            optional_args = {}

        # Netmiko possible arguments
        netmiko_argument_map = {
            'port': None,
            'verbose': False,
            'timeout': self.timeout,
            'global_delay_factor': 1,
            'use_keys': False,
            'key_file': None,
            'ssh_strict': False,
            'system_host_keys': False,
            'alt_host_keys': False,
            'alt_key_file': '',
            'ssh_config_file': None,
            'allow_agent': False,
            'keepalive': 30
        }

        # Build dict of any optional Netmiko args
        self.netmiko_optional_args = {
            k: optional_args.get(k, v)
            for k, v in netmiko_argument_map.items()
        }

        self.transport = optional_args.get('transport', 'ssh')
        self.port = optional_args.get('port', 22)

        self.changed = False
        self.loaded = False
        self.backup_file = ''
        self.replace = False
        self.merge_candidate = ''
        self.replace_file = ''
        self.profile = ["ce"]

    def open(self):
        """Open a connection to the device."""
        try:
            if self.transport == 'ssh':
                device_type = 'eltex'
            else:
                raise ConnectionException("Unknown transport: {}".format(self.transport))

            self.device = ConnectHandler(device_type=device_type,
                                         host=self.hostname,
                                         username=self.username,
                                         password=self.password,
                                         **self.netmiko_optional_args)
            # self.device.enable()

        except NetMikoTimeoutException:
            raise ConnectionException('Cannot connect to {}'.format(self.hostname))

    def close(self):
        """Close the connection to the device."""
        if self.changed and self.backup_file != "":
            self._delete_file(self.backup_file)
        self.device.disconnect()
        self.device = None

    def is_alive(self):
        """Return a flag with the state of the SSH connection."""
        null = chr(0)
        try:
            if self.device is None:
                return {'is_alive': False}
            else:
                # для проверки активности соединения отправляем перевод строки
                self.device.send_command('\n')
        except (socket.error, EOFError):
            # If unable to send, we can tell for sure that the connection is unusable,
            # hence return False.
            return {'is_alive': False}
        return {
            'is_alive': self.device.remote_conn.transport.is_active()
        }

    def compare_config(self):
        """
        Compare candidate config with running.
        ! Not implemented
        """

        return ''

    def discard_config(self):
        """
        Discard changes.
        ! Not implemented
        """
        pass

    def get_facts(self):
        """Return a set of facts from the devices."""
        # default values.
        vendor = u'Eltex'
        uptime = -1
        interface_list = []
        serial_number, fqdn, os_version, hostname, model = (u'Unknown', u'Unknown', u'Unknown', u'Unknown', u'Unknown')

        try:
            show_system = self.device.send_command('show system')
            for line in show_system.splitlines():
                if 'System Description:' in line:
                    _, model = line.split('System Description:')
                    model = model.strip()
                if 'System Up Time (days,hour:min:sec):' in line:
                    _, uptime = line.split('System Up Time (days,hour:min:sec):')
                    uptime = self._parse_eltex_uptime(uptime.strip())
                if 'System Name:' in line:
                    _, hostname = line.split('System Name:')
                    hostname = hostname.strip()
        except Exception as err:
            raise Exception('Error execute "show system". {0}'.format(err))

        try:
            show_serial = self.device.send_command('show system id')
            _active_image = False
            row = 0
            for line in show_serial.splitlines():
                if row == 2:
                    s = ' '.join(line.split()).split(' ')
                    if s[-1]:
                        serial_number = s[-1]
                else:
                    row += 1

        except Exception as err:
            raise Exception('Error execute "show system id". {0}'.format(err))

        try:
            show_ver = self.device.send_command('show version')
            _active_image = False
            for line in show_ver.splitlines():
                if 'Active-image' in line:
                    _active_image = True
                if ('Version:' in line) and _active_image:
                    _, os_version = line.split('Version:')
                    os_version = os_version.strip()
                    break
        except Exception as err:
            raise Exception('Error execute "show version". {0}'.format(err))

        try:
            show_interface = self.device.send_command('show interfaces status')
            _head_end = False
            for line in show_interface.splitlines():
                if '-------' in line:
                    _head_end = True
                    continue
                if _head_end:
                    _interface = line.split(' ')[0]
                    if _interface:
                        interface_list.append(_interface.strip())
        except Exception as err:
            raise Exception('Error execute "show interface status". {0}'.format(err))

        try:
            show_vlan = self.device.send_command('show vlan')
            _head_end = False
            for line in show_vlan.splitlines():
                if '----' in line:
                    _head_end = True
                    continue
                if _head_end:
                    _interface = line.strip().split(' ')[0]
                    if _interface and (len(line.strip().split(' ')[-1]) == 1):
                        interface_list.append(_interface.strip())
        except Exception as err:
            raise Exception('Error execute "show vlan". {0}'.format(err))

        return {
            'uptime': int(uptime),
            'vendor': vendor,
            'os_version': str(os_version),
            'serial_number': str(serial_number),
            'model': str(model),
            'hostname': str(hostname),
            'fqdn': fqdn,  # ? fqdn(fully qualified domain name)
            'interface_list': interface_list
        }

    def cli(self, commands):
        """Execute raw CLI commands and returns their output."""
        cli_output = {}
        if type(commands) is not list:
            raise TypeError('Please enter a valid list of commands!')

        for command in commands:
            output = self.device.send_command(command)
            cli_output[str(command)] = output
        return cli_output

    def commit_config(self, **kwargs):
        """
        Commit configuration.
        ! Not implemented
        :param **kwargs:
        """
        pass

    def load_merge_candidate(self, filename=None, config=None):
        """
        Open the candidate config and merge.
        ! Not implemented
        """
        pass

    def load_replace_candidate(self, filename=None, config=None):
        """
        Open the candidate config and replace.
        ! Not implemented
        """
        pass

    def get_interfaces(self):
        """
        Get interface details (last_flapped is not implemented).

        Sample Output:
        {
            "Vlanif3000": {
                "is_enabled": false,
                "description": "",
                "last_flapped": -1.0,
                "is_up": false,
                "mac_address": "0C:45:BA:7D:83:E6",
                "speed": 1000,
                'mtu': 1500
            },
            "Vlanif100": {
                "is_enabled": false,
                "description": "",
                "last_flapped": -1.0,
                "is_up": false,
                "mac_address": "0C:45:BA:7D:83:E4",
                "speed": 1000,
                'mtu': 1500
            }
        }
        """
        interfaces = {}
        show_interfaces = self.device.send_command('show interfaces')
        if not show_interfaces:
            return {}
        # вывод собирается в список текстовых блоков по каждому интерфейсу
        interfaces_data = []
        _temp = ''
        for line in (show_interfaces + '\n\r--------------').splitlines():
            if '--------------' in line:
                if _temp != '':
                    interfaces_data.append(_temp)
                _temp = line + '\n'
            else:
                _temp += line + '\n'

        re_ifname = '(-+)( show interfaces )(?P<ifname>[a-zA-Z]+[0-9/]+)(.)(-+)'
        re_ifmac = '(MAC address is )(?P<ifmac>([0-9A-Fa-f]{2}[:-]){5}([0-9A-fa-f]{2}))'
        re_ifup = '(?P<ifup>is up )'
        re_ifdesc = '(Description: )(?P<ifdesc>.*)'
        re_ifmtu = '(Interface MTU is )(?P<ifmtu>[0-9]*)'
        re_ifspeed = '((Full|Half)-duplex, )((?P<ifspeed>[0-9]+)(Mbps))'
        re_ifuptime = '(Link is up for )((?P<days>[0-9]+) days, )((?P<hours>[0-9]+) hours, )((?P<minutes>[0-9]+) minutes and )((?P<seconds>[0-9]+) seconds)'

        try:
            for data in interfaces_data:
                interface_name = ''
                interface_is_enabled = False
                interface_description = ''
                interface_last_flapped = -1
                interface_is_up = False
                interface_mac_address = ''
                interface_speed = 0
                interface_mtu = 0

                match_ifname = re.search(re_ifname, data, flags=re.M)
                if match_ifname:
                    interface_name = match_ifname.group('ifname')

                match_ifmac = re.search(re_ifmac, data, flags=re.M)
                if match_ifmac:
                    interface_mac_address = match_ifmac.group('ifmac')

                match_ifup = re.search(re_ifup, data, flags=re.M)
                if match_ifup:
                    interface_is_up = True
                    interface_is_enabled = True

                match_ifdesc = re.search(re_ifdesc, data, flags=re.M)
                if match_ifdesc:
                    interface_description = match_ifdesc.group('ifdesc')

                match_ifmtu = re.search(re_ifmtu, data, flags=re.M)
                if match_ifmtu:
                    interface_mtu = int(match_ifmtu.group('ifmtu'))

                match_ifspeed = re.search(re_ifspeed, data, flags=re.M)
                if match_ifspeed:
                    interface_speed = int(match_ifspeed.group('ifspeed'))

                match_ifuptime = re.search(re_ifuptime, data, flags=re.M)
                if match_ifuptime:
                    interface_last_flapped = int(match_ifuptime.group('days')) * 24 * 60 * 60 + int(
                        match_ifuptime.group('hours')) * 60 * 60 + int(match_ifuptime.group('minutes')) * 60 + int(
                        match_ifuptime.group('seconds'))

                interfaces.update({
                    interface_name: {
                        'description': interface_description,
                        'is_enabled': interface_is_enabled,
                        'is_up': interface_is_up,
                        'last_flapped': interface_last_flapped,
                        'mac_address': interface_mac_address,
                        'speed': interface_speed,
                        'mtu': interface_mtu
                    }
                })
        except Exception as err:
            raise Exception('Error parse interface data. {0}'.format(err))

        return interfaces

    def get_interfaces_ip(self):
        """
        Get interface IP details. Returns a dictionary of dictionaries.

        Sample output:
        {
            "LoopBack0": {
                "ipv4": {
                    "192.168.0.9": {
                        "prefix_length": 32
                    }
                }
            },
            "Vlanif2000": {
                "ipv4": {
                    "192.168.200.3": {
                        "prefix_length": 24
                    },
                    "192.168.200.6": {
                        "prefix_length": 24
                    },
                    "192.168.200.8": {
                        "prefix_length": 24
                    }
                },
                "ipv6": {
                    "FC00::1": {
                        "prefix_length": 64
                    }
                }
            }
        }
        """
        interfaces_ip = {}
        show_v4 = self.device.send_command('show ip interface')
        # show_v6 = self.device.send_command('show ipv6 interface')

        if not show_v4:
            return {}

        re_ipv4 = re.compile('(?P<addr>((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))(\/(?P<mask>(3[0-2]?|[1-2]?[0-9])?))(\s+)(?P<eth>.*)(\s+)(UP|DOWN)')

        interfaces = {}

        try:
            ips = [n.groupdict() for n in re_ipv4.finditer(show_v4)]
            for ip in ips:
                eth = ip['eth'].strip()
                if eth not in interfaces:
                    interfaces.update({
                        eth: {
                            'ipv4': {}
                        }
                    })
                interfaces[eth]['ipv4'].update({
                    ip['addr']: {
                        'prefix_length': ip['mask']
                    }
                })
        except Exception as err:
            raise Exception('Error parse interface addresses. {0}'.format(err))

        return interfaces

    def get_interfaces_counters(self):
        """Return interfaces counters."""
        interfaces = {}

        show_interfaces = self.device.send_command('show interfaces')
        if not show_interfaces:
            return {}

        # вывод собирается в список текстовых блоков по каждому интерфейсу
        data_block = []
        _temp = ''
        for line in (show_interfaces + '\n\r--------------').splitlines():
            if '--------------' in line:
                if _temp != '':
                    data_block.append(_temp)
                _temp = line + '\n'
            else:
                _temp += line + '\n'



        re_ifname = '(-+)( show interfaces )(?P<ifname>[a-zA-Z]+[0-9/]+)(.)(-+)'
        re_inerr = '(?P<in_err>\d+)( input errors)'
        re_outerr = '(?P<out_err>\d+)( output errors)'


        try:
            for data in data_block:
                interface_name = ''
                interface_in_error = 0
                interface_out_error = 0

                match_ifname = re.search(re_ifname, data, flags=re.M)
                if match_ifname:
                    interface_name = match_ifname.group('ifname')

                match_ifinerr = re.search(re_inerr, data, flags=re.M)
                if match_ifinerr:
                    interface_in_error = match_ifinerr.group('in_err')

                match_ifouterr = re.search(re_outerr, data, flags=re.M)
                if match_ifouterr:
                    interface_out_error = match_ifouterr.group('out_err')

                interfaces.update({
                    interface_name: {
                        'tx_error': int(interface_out_error),
                        'rx_error': int(interface_in_error),
                        'tx_discards': 0,
                        'rx_discards': 0,
                        'tx_octets': 0,
                        'rx_octets': 0,
                        'tx_unicast_packets': 0,
                        'rx_unicast_packets': 0,
                        'tx_multicast_packets': 0,
                        'rx_multicast_packets': 0,
                        'tx_broadcast_packets': 0,
                        'rx_broadcast_packets': 0

                    }
                })
        except Exception as err:
            raise Exception('Error parse interface counters. {0}'.format(err))

        # данные выдаются в несколько таблиц
        show_interfaces = self.device.send_command('show interfaces counters')
        data_block = -1     # это состояние блока данных, пока читается заголово, он нафиг не нужен
        data_part = 1       # какую таблицу сейчас читает, там их идет две, одна с tx другая с rx
        if not show_interfaces:
            return {}

        try:
            # режем вывод на строки и собираем блоки из таблиц
            for line in (show_interfaces + '\n\r').splitlines():
                if data_block != -1 and line != '':
                    # если заголовок уже прошли и не наткнулись на конец страницы, то продолжаем собирать блок
                    data_block += line + "\n"
                if line == '':
                    # если дошли до конца таблицы, то начинаем ее разбирать

                    # временная переменная, что бы хранить преыдущую строку
                    # т.к. если данные не вошли в строку, то они продолжаются на следующей
                    prev = None

                    # кормим текст панде, она отдает таблицу, говорим, что заголовка нет и что все данные текстовые
                    d = pd.read_fwf(StringIO(data_block), header=None, dtype={0: str, 1: str, 2: str, 3: str, 4: str})

                    # пошли по строкам
                    for i in d.index:
                        row = d.values[i]
                        # если идет таблица с rx
                        if data_part == 1:
                            # если наткнулись на "перенесенные" данные, то добавляем их в прошлой строке
                            if str(row[0]) == 'nan':
                                interfaces[prev[0]].update({
                                    'rx_octets': interfaces[prev[0]]['rx_octets'] + ('' if str(row[4]) == 'nan' else row[4]),
                                    'rx_unicast_packets': interfaces[prev[0]]['rx_unicast_packets'] + ('' if str(row[1]) == 'nan' else row[1]),
                                    'rx_multicast_packets': interfaces[prev[0]]['rx_multicast_packets'] + ('' if str(row[2]) == 'nan' else row[2]),
                                    'rx_broadcast_packets': interfaces[prev[0]]['rx_broadcast_packets'] + ('' if str(row[3]) == 'nan' else row[3])
                                })
                            else:
                                interfaces[row[0]].update({
                                    'rx_octets': row[4],
                                    'rx_unicast_packets': row[1],
                                    'rx_multicast_packets': row[2],
                                    'rx_broadcast_packets': row[3]
                                })
                                prev = row
                        # если идет таблица rx
                        else:
                            if str(row[0]) == 'nan':
                                interfaces[prev[0]].update({
                                    'tx_octets': interfaces[prev[0]]['tx_octets'] + ('' if str(row[4]) == 'nan' else row[4]),
                                    'tx_unicast_packets': interfaces[prev[0]]['tx_unicast_packets'] + ('' if str(row[1]) == 'nan' else row[1]),
                                    'tx_multicast_packets': interfaces[prev[0]]['tx_multicast_packets'] + ('' if str(row[2]) == 'nan' else row[2]),
                                    'tx_broadcast_packets': interfaces[prev[0]]['tx_broadcast_packets'] + ('' if str(row[3]) == 'nan' else row[3])
                                })
                            else:
                                interfaces[row[0]].update({
                                    'tx_octets': row[4],
                                    'tx_unicast_packets': row[1],
                                    'tx_multicast_packets': row[2],
                                    'tx_broadcast_packets': row[3]
                                })
                                prev = row

                    data_block = -1
                    if data_part == 1:
                        data_part = 2
                    else:
                        data_part = 1
                if '-------' in line:
                    data_block = ''
        except Exception as err:
            raise Exception('Error parse interface counters. {0}'.format(err))

        return interfaces

    def get_environment(self):
        """
        Return environment details.

        Sample output:
        {
            "cpu": {
                "0": {
                    "%usage": 18.0
                }
            },
            "fans": {
                "FAN1": {
                    "status": true
                }
            },
            "memory": {
                "available_ram": 3884224,
                "used_ram": 784552
            },
            "power": {
                "PWR1": {
                    "capacity": 600.0,
                    "output": 92.0,
                    "status": true
                }
            },
            "temperature": {
                "CPU": {
                    "is_alert": false,
                    "is_critical": false,
                    "temperature": 45.0
                }
            }
        }
        """
        environment = {
            'cpu': {
                '0': {
                    '%usage': 0.0
                }
            },
            'fans': {
                'FAN1': {
                    'status': True
                }
            },
            'memory': {
                'available_ram': 0,
                'used_ram': 0
            },
            'power': {
                'PWR1': {
                    'capacity': 0.0,
                    'output': 0.0,
                    'status': True
                }
            },
            'temperature': {
                'CPU': {
                    'is_alert': False,
                    'is_critical': False,
                    'temperature': 0.0
                }
            }
        }

        return environment

    def get_arp_table(self, vrf=""):
        """
        Get arp table information.

        Return a list of dictionaries having the following set of keys:
            * interface (string)
            * mac (string)
            * ip (string)
            * age (float)

        Sample output:
            [
                {
                    'interface' : 'MgmtEth0/RSP0/CPU0/0',
                    'mac'       : '5c:5e:ab:da:3c:f0',
                    'ip'        : '172.17.17.1',
                    'age'       : -1
                },
                {
                    'interface': 'MgmtEth0/RSP0/CPU0/0',
                    'mac'       : '66:0e:94:96:e0:ff',
                    'ip'        : '172.17.17.2',
                    'age'       : -1
                }
            ]
        """
        if vrf:
            msg = "VRF support has not been implemented."
            raise NotImplementedError(msg)

        arp_table = []
        show_arp = self.device.send_command('show arp')

        if not show_arp:
            return {}

        try:
            data_block = -1
            for line in show_arp.splitlines():
                if data_block != -1:
                    data_block += line + '\n\r'
                if '-----' in line:
                    data_block = ''
            d = pd.read_fwf(StringIO(data_block), header=None, dtype={0: str, 1: str, 2: str, 3: str, 4: str})
            for i in d.index:
                row = d.values[i]
                arp_table.append({
                    'interface': row[1],
                    'mac': row[3],
                    'ip': row[2],
                    'age': -1
                })
        except Exception as err:
            raise Exception('Error parse arp table. {0}'.format(err))
        return arp_table

    def get_config(self, retrieve="all", full=False, sanitized=False):
        """
        Get config from device.

        Returns the running configuration as dictionary.
        The candidate and startup are always empty string for now,
        since CE does not support candidate configuration.
        """
        config = {
            'startup': '',
            'running': '',
            'candidate': ''
        }

        if retrieve.lower() in ('running', 'all'):
            command = 'show running-config'
            config['running'] = str(self.device.send_command(command))
        if retrieve.lower() in ('startup', 'all'):
            command = 'show startup-config'
            config['startup'] = str(self.device.send_command(command))
        return config

    def get_lldp_neighbors(self):
        """
        Return LLDP neighbors details.

        Sample output:
        {
            "10GE4/0/1": [
                {
                    "hostname": "HUAWEI",
                    "port": "10GE4/0/25"
                },
                {
                    "hostname": "HUAWEI2",
                    "port": "10GE4/0/26"
                }
            ]
        }
        """

        def mask_device_id(id):
            # if device id look like "43 c5 dd f9 10" replace space on _
            return id.group(0).replace(' ', '_')

        def demask_device_id(id):
            # device id look like "43_c5_dd_f9_10" replace _ on space
            return id.group(0).replace('_', ' ')

        neighbors = {}

        show_neighbors = self.device.send_command('show lldp neighbors')
        show_neighbors = re.sub('(([0-9A-Fa-f]{2}[ ]){4}([0-9A-Fa-f]{2}))', mask_device_id, show_neighbors)

        if not show_neighbors:
            return {}

        try:
            data_block = -1
            for line in show_neighbors.splitlines():
                if data_block != -1:
                    # if '                          ' in line:
                    #     line = ';' + line
                    data_block += ';'.join(str(line).replace('                 ', ';').replace(', ', '-').strip().split()) + '\n\r'
                if '------' in line:
                    data_block = ''
            # print(data_block)
            d = pd.read_csv(StringIO(data_block), delimiter=';', header=None, dtype={0: str, 1: str, 2: str, 3: str, 4: str, 5: str})
            prev = 0
            # пошли по строкам
            for i in d.index:
                row = d.values[i]
                # если наткнулись на "перенесенные" данные, то добавляем их в прошлой строке
                if str(row[0]) == 'nan':
                    _hostname = ''
                    _port = ''
                    if str(row[1]) != 'nan':
                        _port = str(row[1])
                    if str(row[2]) != 'nan':
                        _hostname = str(row[2])
                    # print(row, row[1], row[2], len(row), _port, _hostname, neighbors[prev[0]])
                    neighbors[prev[0]][0] = {
                        'hostname': neighbors[prev[0]][0]['hostname'] + _hostname,
                        'port': neighbors[prev[0]][0]['port'] + _port
                    }
                else:
                    neighbors.update({row[0]: []})
                    neighbors[row[0]].append({
                        # в хост пишем system name, если его нет, то используем divice id
                        # если device id был формата aa aa aa aa aa, то он выше был обращен в aa_aa_aa_aa_aa
                        # тогда возвращаем device id в прежний формат
                        'hostname': (re.sub('(([0-9A-Fa-f]{2}[_]){4}([0-9A-Fa-f]{2}))', demask_device_id, str(row[1])) if str(row[3]) == 'nan' else str(row[3])),
                        'port': str(row[2])
                    })
                    prev = row

        except Exception as err:
            raise Exception('Error parse lldp neighbors. {0}'.format(err))

        return neighbors

    def get_mac_address_table(self):
        """
        Return the MAC address table.

        Sample output:
        [
            {
                "active": true,
                "interface": "10GE1/0/1",
                "last_move": -1.0,
                "mac": "00:00:00:00:00:33",
                "moves": -1,
                "static": false,
                "vlan": 100
            },
            {
                "active": false,
                "interface": "10GE1/0/2",
                "last_move": -1.0,
                "mac": "00:00:00:00:00:01",
                "moves": -1,
                "static": true,
                "vlan": 200
            }
        ]
        """
        mac_address_table = []
        show_mac = self.device.send_command('show mac address-table')
        if not show_mac:
            return []

        try:
            data_block = -1
            for line in show_mac.splitlines():
                if data_block != -1:
                    data_block += line + '\n\r'
                if '-----' in line:
                    data_block = ''
            d = pd.read_fwf(StringIO(data_block), header=None, dtype={0: str, 1: str, 2: str, 3: str})
            for i in d.index:
                row = d.values[i]
                mac_address_table.append({
                    "active": True,
                    "interface": row[2],
                    "last_move": -1.0,
                    "mac": row[1],
                    "moves": -1,
                    "static": (False if row[3] == 'dynamic' else True),
                    "vlan": row[0]
                })
        except Exception as err:
            raise Exception('Error parse mac address table. {0}'.format(err))
        return mac_address_table

    def get_users(self):
        """
        Return the configuration of the users.

        Sample output:
        {
            "admin": {
                "level": 3,
                "password": "",
                "sshkeys": []
            }
        }
        """
        users = {}
        # command = 'display aaa local-user'

        return users

    def rollback(self):
        """
        Rollback to previous commit.
        ! Not implemented
        """
        pass

    def ping(self, destination, source=c.PING_SOURCE, ttl=c.PING_TTL, timeout=c.PING_TIMEOUT, size=c.PING_SIZE,
             count=c.PING_COUNT, vrf=c.PING_VRF, **kwargs):
        """Execute ping on the device.
        :param **kwargs:
        """
        ping_dict = {}
        command = 'ping'
        # Timeout in milliseconds to wait for each reply, the default is 2000
        # command += ' -t {}'.format(timeout * 1000)
        # Specify the number of data bytes to be sent
        # command += ' -s {}'.format(size)
        # Specify the number of echo requests to be sent
        # command += ' -c {}'.format(count)
        # if source != '':
        #     command += ' -a {}'.format(source)
        command += ' {}'.format(destination)
        output = self.device.send_command(command)

        if 'Error' in output:
            ping_dict['error'] = output
        elif 'PING' in output:
            ping_dict['success'] = {
                'probes_sent': 0,
                'packet_loss': 0,
                'rtt_min': 0.0,
                'rtt_max': 0.0,
                'rtt_avg': 0.0,
                'rtt_stddev': 0.0,
                'results': []
            }

            match_sent = re.search(r"(\d+).+transmitted", output, re.M)
            match_received = re.search(r"(\d+).+received", output, re.M)

            try:
                probes_sent = int(match_sent.group(1))
                probes_received = int(match_received.group(1))
                ping_dict['success']['probes_sent'] = probes_sent
                ping_dict['success']['packet_loss'] = probes_sent - probes_received
            except Exception:
                msg = "Unexpected output data:\n{}".format(output)
                raise ValueError(msg)

            match = re.search(r"min/avg/max = (\d+)/(\d+)/(\d+)", output, re.M)
            if match:
                ping_dict['success'].update({
                    'rtt_min': float(match.group(1)),
                    'rtt_avg': float(match.group(2)),
                    'rtt_max': float(match.group(3)),
                })

                results_array = []
                match = re.findall(r"Reply from.+time=(\d+)", output, re.M)
                for i in match:
                    results_array.append({'ip_address': str(destination),
                                          'rtt': float(i)})
                ping_dict['success'].update({'results': results_array})
        return ping_dict

    def __get_snmp_information(self):
        snmp_information = {}
        # command = 'display snmp-agent sys-info'
        # output = self.device.send_command(command)

        snmp_information = {
            'contact': str(''),
            'location': str(''),
            'community': {},
            'chassis_id': str('')
        }
        return snmp_information

    def __get_lldp_neighbors_detail(self, interface=''):
        """
        Return a detailed view of the LLDP neighbors as a dictionary.
        ! Not implemented

        Sample output:
        {
        'TenGigE0/0/0/8': [
            {
                'parent_interface': u'Bundle-Ether8',
                'remote_chassis_id': u'8c60.4f69.e96c',
                'remote_system_name': u'switch',
                'remote_port': u'Eth2/2/1',
                'remote_port_description': u'Ethernet2/2/1',
                'remote_system_description': u'''huawei os''',
                'remote_system_capab': u'B, R',
                'remote_system_enable_capab': u'B'
            }
        ]
        }
        """
        lldp_neighbors = {}
        return lldp_neighbors

    def __get_ntp_peers(self):
        """
        Return the NTP peers configuration as dictionary.
        ! Not implemented

        Sample output:
        {
            '192.168.0.1': {},
            '17.72.148.53': {},
            '37.187.56.220': {},
            '162.158.20.18': {}
        }
        """
        ntp_server = {}
        # command = "display ntp session"
        # output = self.device.send_command(command)
        return ntp_server

    def __get_ntp_servers(self):
        """
        Return the NTP servers configuration as dictionary.
        ! Not implemented

        Sample output:
        {
            '192.168.0.1': {},
            '17.72.148.53': {},
            '37.187.56.220': {},
            '162.158.20.18': {}
        }
        """
        ntp_server = {}
        # command = "display ntp trace"
        # output = self.device.send_command(command)
        return ntp_server

    def __get_ntp_stats(self):
        """
        ! Not implemented
        """
        ntp_stats = []
        # command = "display ntp status"
        # output = self.device.send_command(command)
        return ntp_stats

    @staticmethod
    def _separate_section(separator, content):
        if content == "":
            return []

        # Break output into per-interface sections
        interface_lines = re.split(separator, content, flags=re.M)

        if len(interface_lines) == 1:
            msg = "Unexpected output data:\n{}".format(interface_lines)
            raise ValueError(msg)

        # Get rid of the blank data at the beginning
        interface_lines.pop(0)

        # Must be pairs of data (the separator and section corresponding to it)
        if len(interface_lines) % 2 != 0:
            msg = "Unexpected output data:\n{}".format(interface_lines)
            raise ValueError(msg)

        # Combine the separator and section into one string
        intf_iter = iter(interface_lines)

        try:
            new_interfaces = [line + next(intf_iter, '') for line in intf_iter]
        except TypeError:
            raise ValueError()
        return new_interfaces

    def _delete_file(self, filename):
        """
        ! Not implemented
        """
        #command = 'delete /unreserved /quiet {0}'.format(filename)
        #self.device.send_command(command)
        pass

    def _save_config(self, filename=''):
        """
        Save the current running config to the given file.
        ! Not implemented
        """
        pass
        #command = 'save {}'.format(filename)

    def _load_config(self, config_file):
        """
        ! Not implemented
        """
        pass

    def _replace_candidate(self, filename, config):
        """
        ! Not implemented
        """
        pass

    def _verify_remote_file_exists(self, dst, file_system='flash:'):
        """
        ! Not implemented
        """
        pass

    def _check_file_exists(self, cfg_file):
        """
        ! Not implemented
        """
        return True

    def _check_md5(self, dst):
        """
        ! Not implemented
        """

        return False

    @staticmethod
    def _get_local_md5(dst, blocksize=2 ** 20):
        md5 = hashlib.md5()
        local_file = open(dst, 'rb')
        buf = local_file.read(blocksize)
        while buf:
            md5.update(buf)
            buf = local_file.read(blocksize)
        local_file.close()
        return md5.hexdigest()

    def _get_remote_md5(self, dst):
        """
        ! Not implemented
        """

        return ''

    def _commit_merge(self):
        """
        ! Not implemented
        """
        pass

    def _get_merge_diff(self):
        """
        ! Not implemented
        """
        diff = []
        return '\n'.join(diff)

    def _get_diff(self, filename=None):
        """
        Get a diff between running config and a proposed file.
        ! Not implemented
        """
        return ''

    def _enough_space(self, filename):
        """
        ! Not implemented
        """
        return True

    def _get_flash_size(self):
        """
        ! Not implemented
        """
        return 0

    @staticmethod
    def _parse_eltex_uptime(uptime_str):
        '''
        :param uptime_str: Day,Hour:Minutes:Seconds
        :return: total seconds
        '''

        d = 0
        h = 0
        m = 0
        s = 0

        sub_up_time = ''

        try:
            if ',' in uptime_str:
                _d = uptime_str.split(',')
                if _d[0]:
                    d = int(_d[0])
                else:
                    d = 0
                sub_up_time = _d[1]
            else:
                sub_up_time = uptime_str

            _t = sub_up_time.split(':')

            h = int(_t[0])
            m = int(_t[1])
            s = int(_t[2])
        except Exception as e:
            print('uptime parser: ', e)

        return (d * 60 * 60 * 24) + (h * 60 * 60) + (m * 60) + s

    @staticmethod
    def _parse_uptime(uptime_str):
        """Return the uptime in seconds as an integer."""
        (years, weeks, days, hours, minutes, seconds) = (0, 0, 0, 0, 0, 0)

        years_regx = re.search(r"(?P<year>\d+)\syear", uptime_str)
        if years_regx is not None:
            years = int(years_regx.group(1))
        weeks_regx = re.search(r"(?P<week>\d+)\sweek", uptime_str)
        if weeks_regx is not None:
            weeks = int(weeks_regx.group(1))
        days_regx = re.search(r"(?P<day>\d+)\sday", uptime_str)
        if days_regx is not None:
            days = int(days_regx.group(1))
        hours_regx = re.search(r"(?P<hour>\d+)\shour", uptime_str)
        if hours_regx is not None:
            hours = int(hours_regx.group(1))
        minutes_regx = re.search(r"(?P<minute>\d+)\sminute", uptime_str)
        if minutes_regx is not None:
            minutes = int(minutes_regx.group(1))
        seconds_regx = re.search(r"(?P<second>\d+)\ssecond", uptime_str)
        if seconds_regx is not None:
            seconds = int(seconds_regx.group(1))

        uptime_sec = (years * YEAR_SECONDS) + (weeks * WEEK_SECONDS) + (days * DAY_SECONDS) + \
                     (hours * 3600) + (minutes * 60) + seconds
        return uptime_sec

    @staticmethod
    def _create_tmp_file(config):
        """
        ! Not implemented
        """

        return ''

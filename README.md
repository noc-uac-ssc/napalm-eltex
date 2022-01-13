# NAPALM_ELTEX #

Napalm driver for Eltes switches.

## Requirements

* napalm (3.3)
* pandas (1.3.5) (_pandas is needed to parse fucking tables_)

see requirements.txt

## Implemented methods

_**open()**_ - Open a connection to the device.

<blockquote><pre><code>driver = get_network_driver('eltex')
device = driver(
                device_type=device_type, 
                host=self.hostname, 
                username=self.username, 
                password=self.password
                optional_args={
                    'port': 22
                }
           )
device.open()
...
...
device.close()</code></pre></blockquote>

_**close()**_ - Close the connection to the device.

> <pre><code>device.close()</code></pre>

_**is_alive()**_ - Return a flag with the state of the SSH connection.

> <pre><code>device.is_alive()</code></pre>

_**get_facts()**_ - Return a set of facts from the devices.

> <pre><code>facts = device.get_facts()
> print(facts)</code></pre>

return:

<blockquote><pre><code>{
    'uptime': 7502146, 
    'vendor': 'Eltex', 
    'os_version': '4.0.14.3', 
    'serial_number': 'Unknown', 
    'model': 'MES2324P AC 28-port 1G/10G Managed Switch with 24 POE+ ports', 
    'hostname': '001.209.F2.MES2324PWR.1540024', 
    'fqdn': 'Unknown', 
    'interface_list': [
        'gi1/0/1', 
        'gi1/0/2', 
        'gi1/0/3', 
        'te1/0/1', 
        'te1/0/2',
        ...
        ...
    ]
}</code></pre></blockquote>

_**cli(commands)**_ - Execute raw CLI commands and returns their output.

_**get_interfaces()**_ - Get interface details.

return:
<blockquote><pre><code> {
    'gi1/0/12': {
        'is_enabled': false,
        'description': '',
        'last_flapped': -1.0,
        'is_up': false,
        'mac_address': '0C:45:BA:7D:83:E6',
        'speed': 1000,
        'mtu': 1500
    },
    'gi1/0/13': {
         'is_enabled': true,
         'description': 'USERS',
         'last_flapped': -1.0,
         'is_up': true,
         'mac_address': '0C:45:BA:7D:83:E4',
         'speed': 1000,
         'mtu': 1500
     }
...
...
}</code></pre></blockquote>

_**get_interfaces_ip()**_ - Get interface IP details. Returns a dictionary of dictionaries.

return:
<blockquote><pre><code>{
    'gi1/0/1': {
        'ipv4': {
            '192.168.0.9': {
                'prefix_length': 16
            }
        }
    },
    'Vlan10': {
        'ipv4': {
            '192.168.200.3': {
                'prefix_length': 24
            },
            '192.168.200.6': {
                'prefix_length': 24
            },
            '192.168.200.8': {
                'prefix_length': 24
            }
        }
    }
...
...
}
</code></pre></blockquote>

_**get_interfaces_counters()**_ - Return interfaces counters.

return:
<blockquote><pre><code>{
    'gi1/0/1': 
        {
            'tx_error': 0, 
            'rx_error': 0, 
            'tx_discards': 0, 
            'rx_discards': 0,
            'tx_octets': '4258380107556',
            'rx_octets': '106144858448', 
            'tx_unicast_packets': '4194039722', 
            'rx_unicast_packets': '1396550631', 
            'tx_multicast_packets': '19499222', 
            'rx_multicast_packets': '314766', 
            'tx_broadcast_packets': '14928742', 
            'rx_broadcast_packets': '59701'
    }, 
    'gi1/0/2': 
        {
            'tx_error': 0, 
            'rx_error': 0, 
            'tx_discards': 0, 
            'rx_discards': 0, 
            'tx_octets': '17163865943', 
            'rx_octets': '10026935164', 
            'tx_unicast_packets': '19699662', 
            'rx_unicast_packets': '42074088', 
            'tx_multicast_packets': '19443159', 
            'rx_multicast_packets': '317637', 
            'tx_broadcast_packets': '14916046', 
            'rx_broadcast_packets': '20190'}, 
    }
...
...
}
</code></pre></blockquote>

_**get_environment()**_ - Return environment details.

return:
<blockquote><pre><code>{
    'cpu': {
        '0': {
            '%usage': 18.0
        }
    },
    'fans': {
        'FAN1': {
            'status': true
        }
    },
    'memory': {
        'available_ram': 3884224,
        'used_ram': 784552
    },
    'power': {
        'PWR1': {
            'capacity': 600.0,
            'output': 92.0,
            'status': true
        }
    },
    'temperature': {
        'CPU': {
            'is_alert': false,
            'is_critical': false,
            'temperature': 45.0
        }
    }
}
</code></pre></blockquote>

_**get_arp_table()**_ - Get arp table information.

return:
<blockquote><pre><code>[
    {
        'interface': 'gi1/0/24', 
        'mac': '00:26:cb:32:d1:3f', 
        'ip': '10.154.1.1', 'age': -1
    }, 
    {
        'interface': 'gi1/0/24', 
        'mac': '9c:1d:36:fe:c0:42', 
        'ip': '10.154.1.41', 'age': -1
    }, 
    {
        'interface': 'gi1/0/24', 
        'mac': 'c4:b8:b4:63:44:2b', 
        'ip': '10.154.1.63', 
        'age': -1
    }, 
    {
        'interface': 'gi1/0/24', 
        'mac': 'c4:b8:b4:63:44:36', 
        'ip': '10.154.1.93', 'age': -1
    }, 
...
...
]
</code></pre></blockquote>

_**get_config(retrieve='all|running|startup')**_ - Get config from device.

return:
<blockquote><pre><code>spanning-tree hello-time 1
spanning-tree max-age 6
spanning-tree forward-time 4
!
vlan database
 vlan 19,800
exit
!
voice vlan id 800
voice vlan state oui-enabled
voice vlan oui-table add 805ec0
!
lldp med network-policy 1 voice vlan 800 vlan-type tagged up 5
!
errdisable recovery interval 30
errdisable recovery cause loopback-detection
errdisable recovery cause stp-bpdu-guard
errdisable recovery cause stp-loopback-guard
!
mac address-table notification change
mac address-table notification change history 100
...
...
</code></pre></blockquote>

_**get_lldp_neighbors()**_ - Return LLDP neighbors details.

return:
<blockquote><pre><code>{
    'gi1/0/1': [
        {
            'hostname': 'SIP-T46S', 
            'port': '80:5e:c0:53:82:05'
        }
    ], 
    'gi1/0/2': [
        {
            'hostname': 'SIP-T43U', 
            'port': '80:5e:c0:9e:6b:19'
        }
    ], 
    'gi1/0/3': [
        {
            'hostname': 'SIP-T46S', 
            'port': '80:5e:c0:53:82:ea'
        }
    ], 
    'gi1/0/4': [
        {
            'hostname': 'SIP-T19P_E2', 
            'port': '80:5e:c0:b8:0d:35'
        }
    ],
...
...
}
</code></pre></blockquote>

_**get_mac_address_table()**_ - Return the MAC address table.

return:
<blockquote><pre><code>[
    {
        'active': True, 
        'interface': 'gi1/0/24', 
        'last_move': -1.0, 
        'mac': '00:16:b9:ba:17:c0', 
        'moves': -1, 
        'static': False, 
        'vlan': '1'
    }, 
    {
        'active': True, 
        'interface': 'gi1/0/24', 
        'last_move': -1.0, 
        'mac': '00:18:fe:d4:5b:40', 
        'moves': -1, 
        'static': False, 
        'vlan': '1'
    }, 
    {
        'active': True, 
        'interface': 'gi1/0/24', 
        'last_move': -1.0, 
        'mac': '00:1d:b3:3e:ad:a0', 
        'moves': -1, 
        'static': False, 
        'vlan': '1'
    },
...
...
]
</code></pre></blockquote>

_**get_users**_

return:
<blockquote><pre><code>{
    'admin': {
        'level': 3,
        'password': '',
        'sshkeys': []
    }
}
</code></pre></blockquote>


## Skipped methods ##


compare_config()

discard_config()

commit_config()

load_merge_candidate(filename=None, config=None)

load_replace_candidate(filename=None, config=None)

rollback()

ping(destination, source=c.PING_SOURCE, ttl=c.PING_TTL, timeout=c.PING_TIMEOUT, size=c.PING_SIZE, count=c.PING_COUNT, vrf=c.PING_VRF, **kwargs)

__get_lldp_neighbors_detail(interface='')

__get_ntp_peers()

__get_ntp_servers()

__get_ntp_stats()

_delete_file(filename)

_save_config(filename='')

_load_config(config_file)

_replace_candidate(filename, config)

_verify_remote_file_exists(dst, file_system='flash:')

_check_file_exists(cfg_file)

_check_md5(dst)

_get_remote_md5(dst)

_commit_merge()

_get_merge_diff()

_get_diff(filename=None)

_enough_space(filename)

_get_flash_size()


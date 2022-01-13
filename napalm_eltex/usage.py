from napalm import get_network_driver

if __name__ == '__main__':
    driver = get_network_driver('eltex')
    device = driver(
        hostname='1.1.1.1',
        username='admin',
        password='secure_password',
        optional_args={
            'port': 22
        }
    )
    device.open()

    facts = device.get_facts()
    print('=============== facts ===============')
    print(facts)

    # interfaces = device.get_interfaces()
    # print(interfaces)

    # ip = device.get_interfaces_ip()
    # print(ip)

    # counters = device.get_interfaces_counters()
    # print(counters)

    # arp = device.get_arp_table()
    # print(arp)

    # config = device.get_config()
    # print(config)

    # neighbors = device.get_lldp_neighbors()
    # print(neighbors)

    # mac = device.get_mac_address_table()
    # print(mac)

    device.close()

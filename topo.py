import json
from typing import List, Dict, Tuple, Any

from mininet.node import Controller, RemoteController, OVSController, Host
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.cli import CLI
from mininet.link import TCLink, Intf
from mininet.log import setLogLevel, info
from mininet.topo import Topo

inter_switch_links = [
    ("s1", "s3"),
    ("s1", "s8"),
    ("s3", "s8"),
    ("s3", "s4"),
    ("s3", "s6"),
    ("s8", "s6"),
    ("s8", "s7"),
    ("s6", "s5"),
    ("s5", "s4"),
    ("s5", "s2"),
    ("s5", "s7"),
    ("s4", "s2"),
    ("s4", "s7"),
    ("s2", "s7")
]


def get_hosts(cnt) -> List[Dict[str, str]]:
    res = []
    for i in range(1, cnt + 1):
        res.append({
            "name": f"h{i}",
            "mac": f"01:00:00:00:0{i}:00",
            "ip": f"192.168.0.{i}/24"
        })
    return res


def get_switches(cnt) -> List[Dict[str, str]]:
    res = []
    for i in range(1, cnt + 1):
        res.append({
            "name": f"s{i}",
            "mac": f"01:00:00:00:00:0{i}"
        })
    return res


def get_default_links(cnt) -> List[Tuple[str, str]]:
    return [(f"s{i}", f"h{i}") for i in range(1, cnt + 1)]


config = {
    "links": [],
    "switches": [],
    "hosts": []
}


def topo():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)

    info('*** Adding controll\n')
    c0 = net.addController(name='c0', controller=RemoteController, ip='127.0.0.1', protocol='tcp', port=6633)

    info('*** Add host\n')

    nodes: Dict[str, Any] = dict()

    hosts: Dict[str, Host] = dict()
    # Create nodes
    for host_info in get_hosts(8):
        tmp = net.addHost(**host_info)
        nodes[host_info["name"]] = tmp
        hosts[host_info["name"]] = tmp

        config['hosts'].append(host_info)

    switches: Dict[str, Host] = dict()
    # Create switches
    for switch_info in get_switches(8):
        tmp = net.addSwitch(**switch_info)
        nodes[switch_info["name"]] = tmp
        switches[switch_info["name"]] = tmp

        config['switches'].append(switch_info)

    # Create Links
    for link in get_default_links(8) + inter_switch_links:
        link = net.addLink(node1=nodes[link[0]], node2=nodes[link[1]], bw=1000, delay="1")
        config['links'].append((link.intf1.name, link.intf2.name))

    net.build()
    c0.start()

    info('***Starting switches\n')
    for switch_name in switches.keys():
        net.get(switch_name).start([c0])

    CLI(net)
    net.stop()

topo()

json.dump(config, open("config.json", "w"))

import json
import logging
from queue import PriorityQueue
from typing import DefaultDict

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, arp
from ryu.ofproto import ofproto_v1_3
from collections import defaultdict

import random


class ProjectController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ProjectController, self).__init__(*args, **kwargs)
        self.graph = defaultdict(lambda: list())
        self.config = json.load(open("config.json", 'r'))
        self.hosts = dict()
        self.switches = dict()
        for host in self.config['hosts']:
            self.hosts[host['name']] = host

        for switch in self.config['switches']:
            self.switches[switch['name']] = switch

        for link in self.config['links']:
            link.append(random.randint(1, 10))
        self.create_graph()

    def create_graph(self):
        self.logger.info("----graph-----")
        self.logger.info("--s1  s2  w--")
        tmp1 = []
        tmp2 = []
        for link in self.config['links']:
            s1, port1 = link[0].split('-')
            s2, port2 = link[1].split('-')
            w = link[2]
            self.graph[s1].append((s2, w, port1))
            self.graph[s2].append((s1, w, port2))
            self.logger.info(f"{s1} {s2} {w}\n")
            tmp2.append(f"{s1} {s2} {w}")
            tmp1.append(f"{s1} {port1} {s2}")
            tmp1.append(f"{s2} {port1} {s1}")
        tmp1 = sorted(tmp1)
        tmp2 = sorted(tmp2)
        with open("graph.log", "w") as f:
            for s in tmp2:
                print(s, file=f)
            for s in tmp1:
                print(s, file=f)

    def get_min_dists(self, src: str):
        q = PriorityQueue()
        for v, w, port in self.graph[src]:
            q.put((w, v, port))

        seen: DefaultDict[str, bool] = defaultdict(lambda: False)
        seen[src] = True

        res = []

        while not q.empty():
            self.logger.info("queue loop")
            dist, node, port = q.get()

            if seen[node]:
                continue
            seen[node] = True
            res.append((node, port))

            for v, w, _ in self.graph[node]:
                if not seen[v]:
                    q.put((dist + w, v, port))

        return res

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        src = f"s{datapath.id}"

        res = self.get_min_dists(src)

        out_port: str
        for node, out_port in res:
            self.logger.info(f"{src} to {node} by port {out_port}")
            if node in self.hosts:
                ip = self.hosts[node]['ip'].split('/')[0]
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=ip)
                self.add_flow(datapath, 1, match, [parser.OFPActionOutput(int(out_port[3:]))])

                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_ARP,
                    arp_tpa=ip,
                    arp_op=arp.ARP_REQUEST
                )
                self.add_flow(datapath, 1, match, [parser.OFPActionOutput(int(out_port[3:]))])

                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_ARP,
                    arp_tpa=ip,
                    arp_op=arp.ARP_REPLY
                )
                self.add_flow(datapath, 1, match, [parser.OFPActionOutput(int(out_port[3:]))])

                mac = self.hosts[node]['mac']

                self.logger.info(f"{node} is a host")
            else:
                mac = self.switches[node]['mac']

                self.logger.info(f"{node} is a switch")
            match = parser.OFPMatch(eth_dst=mac)
            self.add_flow(datapath, 1, match, [parser.OFPActionOutput(int(out_port[3:]))])

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    @staticmethod
    def add_flow(datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

**本文以Xrayr作为后端程序，soga等可以根据原理自行摸索，不难。**

## 1、前提条件

使用国内服务器的中转机场、拥有国内服务器的root权限、拥有一个使用专线的socks5代理（不使用专线也行，专线只是为了让劫持后的延迟更好看）。

## 2、网络架构

#### 2.1、正常情况下的网络架构

![](https://s2.loli.net/2023/10/29/YBhmCD8ubNjq9lp.png)

#### 2.2、劫持后的网络架构

![](https://s2.loli.net/2023/10/29/R4xSAZ3Gjp9b1u2.png)

## 3、原理讲解

既然要在国内服务器上劫持流量，那么我们分流的时候流量必须是未加密的，不然我们怎么知道哪些请求是测延迟的，哪些请求是正常访问。所以我们需要在国内服务器上安装Xrayr，并与V2board进行对接，将所有的节点放在国内服务器上（config.yml文件内的Nodes部分），这样用户来的请求在Xrayr内就是未加密的流量，就可以通过router路由功能将特定的几个测延迟的域名分流出来，其余请求通过custom_outbound发送出去，走正常的跨境隧道到落地机。

那么肯定就有人要问了，落地机上的Xrayr不和V2board对接，那他怎么接收流量？事实上，**落地机是和国内服务器进行对接**，在我的方案内，我通过SS将国内机分流后的正常流量重新加密，发送到落地机，落地机再进行解密，发送到互联网中。

对于分流出来的测延迟的请求，要将其划分为HTTP流量和HTTPS流量分别处理。HTTP流量不验证SSL证书，所以我们可以在本地搭建一个伪站，在我的方案内，我使用Python Flask框架直接返回204状态码，你如果想使用Nginx也完全没有问题。HTTPS流量因为需要验证SSL证书，而这个证书我们肯定没有，也就不可能搭建伪站，所以这些请求最终只能到达真实的网站。有一个技术叫做Sniproxy，可以在不解密SSL的情况下反向代理HTTPS流量，我们就利用Sniproxy将这些HTTPS流量反向代理到真实的网站，再给Sniproxy套一个socks5代理，尽可能地减少延迟。

经过了以上的操作，我们再来梳理一下各类流量是怎样“流动”的。

- 非延迟测试流量：用户发送到国内服务器——国内服务器入口解密——分流——国内服务器出口加密——隧道跨境——落地机解密——互联网

- 延迟测试流量：用户发送到国内服务器——国内服务器入口解密——分流——HTTP流量直接在本地返回，HTTPS流量走IPLC到境外真实网站

HTTP延迟为**用户到国内服务器的延迟**，HTTPS延迟为**用户到国内服务器再经过IPLC到境外的延迟**。

## 4、量子专线，启动！

对于每一个节点，共需要三个端口号：

- V2board面板端口
- 隧道入口端口
- 落地SS端口

在PortForwardGo、咸蛋等端口转发程序中，应当设置本地端口为隧道入口端口，远程地址为落地机IP，远程端口为落地SS端口的转发规则。

```
例：对于HK01，面板端口设置为10001，本地端口30001转发至远程地址114.114.114.114，远程端口60001
```

#### 4.1、V2board面板配置

一个常见的中转节点在V2后台通常会分为落地和中转两个节点，两个节点的配置中会出现4个端口，全部设置为相同的。

![image-20231029134613849](https://s2.loli.net/2023/10/29/xcCFDe3qgMAOUWI.png)

![image-20231029134647257](https://s2.loli.net/2023/10/29/8aTAnPg5xzRHqNf.png)

#### 4.2、国内机安装Xrayr

一键脚本如下，卡住的话给服务器挂一个代理

```
wget -N https://raw.githubusercontent.com/XrayR-project/XrayR-release/master/install.sh && bash install.sh

# 服务器套Socks5代理，仅当前终端生效，断开SSH后失效
export all_proxy="socks5://ip:port"
export ALL_PROXY="socks5://ip:port"
```

#### 4.3、国内机安装Python、Sniproxy

```
apt update && apt install python3-pip -y
pip3 install flask
mkdir /root/sni
ulimit -n 65535
```

将Github仓库中sni文件夹内的文件上传到/root/sni下，修改config.yaml内的配置，一般情况下只需要更改socks5地址即可：

```
# 监听端口（注意需要引号）
listen_addr: ":443"

# 可选：启用 Socks5 前置代理
enable_socks5: true
# 可选：配置 Socks5 代理地址
socks_addr: ip:port

# 可选：允许所有域名（会忽略下面的 rules 列表）
#allow_all_hosts: true

# 可选：仅允许指定域名
rules:
  - gstatic.com
  - cloudflare.com
```

```
chmod +x /root/sni/sniproxy
vim /etc/systemd/system/sniproxy.service
```

输入法切换到英文，先按i，然后粘贴下面的内容：

```
[Unit]
Description=SNI Proxy
After=network.target

[Service]
ExecStart=/root/sni/sniproxy -c /root/sni/config.yaml -l /root/sni/sni.log
Restart=always
RestartSec=30
StartLimitInterval=120
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

再按esc，输入:wq，回车。

```
nohup python3 /root/sni/204.py  > /root/sni/204.log 2>&1 &
systemctl restart sniproxy.service
systemctl enable sniproxy.service
systemctl status sniproxy.service
显示active即可。
```

yysy，以上的步骤你如果卡住了，真别开机场了，开了也是祸害人。

#### 4.5、落地机Xrayr配置

*我不知道该怎么解释，就直接放例子了，希望你与我心灵相通。*

如果需要流媒体解锁就和以前一样配置。config.yml内删除Nodes部分。

**config.yml：**

```
Log:
  Level: warning # Log level: none, error, warning, info, debug 
  AccessPath: # /etc/XrayR/access.Log
  ErrorPath: # /etc/XrayR/error.log
DnsConfigPath: # /etc/XrayR/dns.json # Path to dns config, check https://xtls.github.io/config/dns.html for help
RouteConfigPath: # /etc/XrayR/route.json # Path to route config, check https://xtls.github.io/config/routing.html for help
InboundConfigPath: /etc/XrayR/custom_inbound.json # Path to custom inbound config, check https://xtls.github.io/config/inbound.html for help
OutboundConfigPath: /etc/XrayR/custom_outbound.json # Path to custom outbound config, check https://xtls.github.io/config/outbound.html for help
ConnectionConfig:
  Handshake: 4 # Handshake time limit, Second
  ConnIdle: 30 # Connection idle time limit, Second
  UplinkOnly: 2 # Time limit when the connection downstream is closed, Second
  DownlinkOnly: 4 # Time limit when the connection is closed after the uplink is closed, Second
  BufferSize: 64 # The internal cache size of each connection, kB
```

**custom_inbound.json：**

这个Shadowsocks是自己约定的，仅用于国内机到落地机之间的传输，所以password就自己生成一个。

```
[
  {
    "tag": "Local-in",
    "listen": "0.0.0.0",
    "port": 落地SS端口,
    "protocol": "Shadowsocks",
    "settings": {
      "password": "和国内机一样",
      "method": "aes-256-gcm",
      "level": 0,
      "network": "tcp,udp"
    },
    "streamSettings": {
      "network": "tcp",
      "security": "none"
    }
  }
]
```

**custom_outbound.json：**

*不解锁流媒体*

```
[
  {
    "tag": "IPv4_out",
    "protocol": "freedom",
    "settings": {}
  },
  {
    "tag": "IPv6_out",
    "protocol": "freedom",
    "settings": {
      "domainStrategy": "UseIPv6"
    }
  },
  {
    "protocol": "blackhole",
    "tag": "block"
  }
]
```

*解锁流媒体*

```
[
  {
    "tag": "IPv4_out",
    "protocol": "freedom",
    "settings": {}
  },
  {
    "tag": "IPv6_out",
    "protocol": "freedom",
    "settings": {
      "domainStrategy": "UseIPv6"
    }
  },
  {
    "tag": "dns_out",
    "protocol": "freedom",
    "settings": {
      "domainStrategy": "UseIP",
      "redirect": ":0",
      "userLevel": 0
    }
  },
  {
    "protocol": "blackhole",
    "tag": "block"
  }
]
```

**route.json：**

*不解锁流媒体*

```
{
  "domainStrategy": "IPOnDemand",
  "rules": [
    {
      "type": "field",
      "outboundTag": "IPv4_out",
      "network": "udp,tcp"
    }
  ]
}
```

*解锁流媒体*

```
{
  "domainStrategy": "AsIs",
  "rules": [
    {
      "type": "field",
      "outboundTag": "dns_out",
      "domain": []
    },
    {
      "type": "field",
      "outboundTag": "IPv4_out",
      "network": "udp,tcp"
    }
  ]
}
```



#### 4.4、国内机Xrayr配置

*我不知道该怎么解释，就直接放例子了，希望你与我心灵相通。*

**config.yml：**

ControllerConfig下的ListenIP需要改成你的入口IP。

```
Log:
  Level: warning # Log level: none, error, warning, info, debug 
  AccessPath: # /etc/XrayR/access.Log
  ErrorPath: # /etc/XrayR/error.log
  dnsLog: true
DnsConfigPath: /etc/XrayR/dns.json # Path to dns config, check https://xtls.github.io/config/dns.html for help
RouteConfigPath: /etc/XrayR/route.json # Path to route config, check https://xtls.github.io/config/routing.html for help
InboundConfigPath: # /etc/XrayR/custom_inbound.json # Path to custom inbound config, check https://xtls.github.io/config/inbound.html for help
OutboundConfigPath: /etc/XrayR/custom_outbound.json # Path to custom outbound config, check https://xtls.github.io/config/outbound.html for help
ConnectionConfig:
  Handshake: 4 # Handshake time limit, Second
  ConnIdle: 30 # Connection idle time limit, Second
  UplinkOnly: 2 # Time limit when the connection downstream is closed, Second
  DownlinkOnly: 4 # Time limit when the connection is closed after the uplink is closed, Second
  BufferSize: 64 # The internal cache size of each connection, kB
Nodes:
  -
    PanelType: "NewV2board" # Panel type: SSpanel, V2board, NewV2board, PMpanel, Proxypanel, V2RaySocks
    ApiConfig:
      ApiHost: ""
      ApiKey: ""
      NodeID: 3
      NodeType: Shadowsocks # Node type: V2ray, Shadowsocks, Trojan, Shadowsocks-Plugin
      Timeout: 30 # Timeout for the api request
      EnableVless: false # Enable Vless for V2ray Type
      EnableXTLS: false # Enable XTLS for V2ray and Trojan
      SpeedLimit: 0 # Mbps, Local settings will replace remote settings, 0 means disable
      DeviceLimit: 10 # Local settings will replace remote settings, 0 means disable
      RuleListPath: # /etc/XrayR/rulelist Path to local rulelist file
    ControllerConfig:
      ListenIP: 入口IP # IP address you want to listen
      SendIP: 0.0.0.0 # IP address you want to send pacakage
      UpdatePeriodic: 60 # Time to update the nodeinfo, how many sec.
      EnableDNS: true # Use custom DNS config, Please ensure that you set the dns.json well
      DNSType: UseIPv4 # AsIs, UseIP, UseIPv4, UseIPv6, DNS strategy
      EnableProxyProtocol: false # Only works for WebSocket and TCP
```

**route.json：**

这里只放了一个节点的例子，实际环境中机场所有的节点都会在这里，自行向下添加节点即可。

```
{
  "domainStrategy": "IPOnDemand",
  "rules": [
    {
      "type": "field",
      "outboundTag": "ping-out",
      "domain": ["gstatic.com","cp.cloudflare.com"]
    },
    {
        "type": "field",
        "outboundTag": "blackhole",
        "protocol": [
            "bittorrent"
        ]
    },
    {
      "type": "field",
      "outboundTag": "HK01",
      "domainMatcher": "hybrid",
      "inboundTag": ["Shadowsocks_入口IP_面板端口"]
    }
  ]
}
```

**custom_outbound.json：**

```
[
    {
        "tag": "HK01",
        "protocol": "Shadowsocks",
        "settings": {
        "servers": [
            {
            "address": "入口IP",
            "port": 隧道入口端口,
            "method": "aes-256-gcm",
            "password": "和落地机一样",
            "uot": true,
            "UoTVersion": 2,
            "level": 0
            }
        ]
        },
        "streamSettings": {
        "network": "tcp",
        "security": "none"
        }
    },
    {
        "tag": "blackhole",
        "protocol": "Blackhole"
    },
    {
        "tag": "ping-out",
        "protocol": "Freedom",
        "settings": {
            "domainStrategy": "UseIP",
            "redirect": "127.0.0.1:0",
            "userLevel": 0
        }
    }
]
```


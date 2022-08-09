<div align="center"> 
<h1 align="center">签到盒青龙版</h1>
</div>

![GitHub stars](https://img.shields.io/github/stars/cddjr/check?style=flat-square)
![GitHub forks](https://img.shields.io/github/forks/cddjr/check?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/cddjr/check?style=flat-square)
![GitHub issues](https://img.shields.io/github/languages/code-size/cddjr/check?style=flat-square)


# 一个运行在青龙的签到函数

[青龙](https://github.com/whyour/qinglong.git)

## 特别声明

- 本仓库发布的脚本及其中涉及的任何解锁和解密分析脚本，仅用于测试和学习研究，禁止用于商业用途，不能保证其合法性，准确性，完整性和有效性，请根据情况自行判断。

- 本项目内所有资源文件，禁止任何公众号、自媒体进行任何形式的转载、发布。

- 本人对任何脚本问题概不负责，包括但不限于由任何脚本错误导致的任何损失或损害。

- 间接使用脚本的任何用户，包括但不限于建立VPS或在某些行为违反国家/地区法律或相关法规的情况下进行传播, 本人对于由此引起的任何隐私泄漏或其他后果概不负责。

- 请勿将本仓库的任何内容用于商业或非法目的，否则后果自负。

- 如果任何单位或个人认为该项目的脚本可能涉嫌侵犯其权利，则应及时通知并提供身份证明，所有权证明，我们将在收到认证文件后删除相关脚本。

- 任何以任何方式查看此项目的人或直接或间接使用该项目的任何脚本的使用者都应仔细阅读此声明。本人保留随时更改或补充此免责声明的权利。一旦使用并复制了任何相关脚本或Script项目的规则，则视为您已接受此免责声明。

**您必须在下载后的24小时内从计算机或手机中完全删除以上内容**

> ***您使用或者复制了本仓库且本人制作的任何脚本，则视为 `已接受` 此声明，请仔细阅读***

## 支持的签到列表

可以在各文件夹查看

#### 1.dailycheckin_scripts：

该文件夹下是 [sitoi/dailycheckin](https://github.com/sitoi/dailycheckin) 该项目的全部支持脚本

[配置方式查看](https://github.com/cddjr/check/blob/master/dailycheckin_scripts/README.md)

AcFun | 百度搜索资源平台 | Bilibili | 天翼云盘 | CSDN | 多看阅读 | 恩山论坛 | Fa米家 | 网易云游戏 | 葫芦侠 | 爱奇艺 | 全民K歌 | MEIZU 社区 | 芒果 TV | 小米运动 | 网易云音乐 | 一加手机社区官方论坛 | 哔咔漫画 | 吾爱破解 | 什么值得买 | 百度贴吧 | V2EX | 腾讯视频 | 微博 | 联通沃邮箱 | 哔咔网单 | 王者营地 | 有道云笔记 | 智友邦 | 机场签到 | 欢太商城 | NGA | 掘金 | GLaDOS | HiFiNi | 时光相册 | 联通营业厅

## 使用方法

**进入容器后运行以下命令**（docker exec -it ql bash）修改ql为你的青龙容器名字

以下命令全部都是进入容器后输入

### 1.拉取仓库

只使用dailycheckin_scripts：

```
ql repo https://github.com/cddjr/check.git "ck_" "" "checksend|utils"
```

只使用others_scripts：

```
ql repo https://github.com/cddjr/check.git "oc_" "" "checksend|utils"
```

我全都要:

```
ql repo https://github.com/cddjr/check.git "ck_|oc_" "" "checksend|utils"
```

### 2.运行以下命令

旧版(青龙v2.12以下)

```shell
cd /ql/repo/cddjr_check && python3 utils.py
```

新版

```shell
cd /ql/data/repo/cddjr_check && python3 utils.py
```

然后不出意外的话你可以在青龙面板的配置文件下找到check.toml或check.json文件

然后根据各文件夹下REDEME修改配置[这里](https://sitoi.gitee.io/dailycheckin/settings/)

### 3.说明

1.本仓库在12.21日的更新中同时支持了json和toml两种格式的配置文件，但是推荐使用toml格式配置文件

2.当toml和json配置文件共存时优先使用toml文件

3.为避免未设置的签到项目推送，请禁止该签到任务，或注释掉配置文件中关于这个任务的配置项目

4.在运行修改运行时间后若出现未知错误

**请先确认database.sqlite.back或crontab.db.back是否存在**,然后

```
cd /ql/data/db/ && rm database.sqlite && cp database.sqlite.back database.sqlite #v2.12+
```

```
cd /ql/db/ && rm database.sqlite && cp database.sqlite.back database.sqlite #v2.11+
```

```
cd /ql/db/ && rm crontab.db && cp crontab.db.back crontab.db #v2.11-
```

### 4.**更新支持了多账号**

toml配置方式

```toml
[[ACFUN]]
password = "Sitoi"
phone = "188xxxxxxxx"

[[ACFUN]]
password = "123456"
phone = "135xxxxxxxx"
```

json配置方式

```json
  "ACFUN" : [
    {
    "password": "Sitoi",
    "phone": "18888xxxxxx"
    },
{
"password": "多账号 密码填写，请参考上面",
"phone": "多账号 手机号填写，请参考上面"
}
],
```

### 5.通知配置

来自于青龙的config.sh

**在2022.4.10更新接入消息推送APP**

环境变量为设置别名的内容

```shell
export MI_PUSH_ALIAS="********"
```

## 其他

#### 1.关于 toml 的语法参考：

* [toml-lang/toml](https://github.com/toml-lang/toml)
* [中文知乎介绍](https://zhuanlan.zhihu.com/p/50412485)
* [TOML 教程中文版](https://toml.io/cn/v1.0.0)

#### 2.排错指引

1.在sitoi/dailycheckin的某次更新中修改了键名，请尽量删除原配置文件后重新配置

2.本库找配置文件时使用了正则表达式,在最外层配置时可以不区分大小写，且只要包含字段就可以，甚至可以写中文(强烈不建议这么写,貌似toml不支持)

3.很多脚本并没有测试

## 致谢

[@Wenmoux](https://github.com/Wenmoux/)  

[@Sitoi](https://github.com/Sitoi)

[@Oreomeow](https://github.com/Oreomeow)


## Stargazers over time

[![Stargazers over time](https://starchart.cc/cddjr/check.svg)](https://starchart.cc/cddjr/check)


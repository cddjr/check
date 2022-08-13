/*
@肥皂 3.22 闲趣赚  一天0.1-0.4或者更高（根据用户等级增加任务次数）
3.24 更新加入用户余额和信息。。。。
苹果&安卓下载地址：复制链接到微信打开   https://a.jrpub.cn/3345249
新人进去直接秒到账两个0.3.。。。（微信登录）花两分钟再完成下新人任务，大概秒到微信3元左右
感觉看账号等级，我的小号进去只能做五个任务，大号可以做十个。
建议做一下里面的任务，单价还是不错的，做完等级升上来了挂脚本收益也多一点。
抓取域名  wap.quxianzhuan.com  抓取cookie的全部数据。。
青龙变量  xqzck  多账户@隔开
更新加入用户余额和信息。。。。
*/
const $ = new Env("闲趣赚3.24");
let status;
status = (status = $.getval("xqzstatus") || "1") > 1 ? "" + status : "";
let xqzckArr = [];
let xqzck = ($.isNode() ? process.env.xqzck : $.getdata("xqzck")) || "";
let reward_id = "", formhash = "";
!(async () => {
	xqzckArr = xqzck.split("@");
	console.log("------------- 共" + xqzckArr.length + "个账号-------------\n");
	for (let i = 0; i < xqzckArr.length; i++) {
		xqzck = xqzckArr[i];
		$.index = i + 1;
		console.log("\n开始【闲趣赚" + $.index + "】");
		await getNextTask();
		await queryUser();
	}
})()
	.catch((e) => $.logErr(e))
	.finally(() => {
		$.done();
	});
function getNextTask() {
	return new Promise(resolve => {
		let options = {
			url: "https://wap.quxianzhuan.com/reward/browse/index/?xapp-target=blank",
			headers: JSON.parse(
				'{"Host":"wap.quxianzhuan.com","Connection":"keep-alive","Upgrade-Insecure-Requests":"1","User-Agent":"Mozilla/5.0 (Linux; Android 10; 16s Pro Build/QKQ1.191222.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.106 Mobile Safari/537.36  XiaoMi/MiuiBrowser/10.8.1 LT-APP/44/200","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9","x-app":"96c1ea5a-9a52-44c9-8ac4-8dceafa065c8","X-Requested-With":"com.quxianzhuan.wap","Sec-Fetch-Site":"none","Sec-Fetch-Mode":"navigate","Sec-Fetch-User":"?1","Sec-Fetch-Dest":"document","Referer":"https://wap.quxianzhuan.com/reward/list/?xapp-target=blank","Accept-Encoding":"gzip, deflate","Accept-Language":"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7","Cookie":"' +
				xqzck +
				'"}'
			),
		};
		$.get(options, async (err, resp, data) => {
			try {
				reward_id = data.match(/reward_id":"(\d+)",/)[1];
				formhash = xqzck.match(/tzb_formhash_cookie=(\w+);/)[1];
				console.log("\n闲趣赚匹配任务ID：" + reward_id);
				await doTask();
			} catch (e) {
			} finally {
				resolve();
			}
		});
	});
}
function doTask() {
	return new Promise(resolve => {
		let options = {
			url: "https://wap.quxianzhuan.com/reward/browse/append/",
			headers: JSON.parse(
				'{"Host":"wap.quxianzhuan.com","Connection":"keep-alive","Upgrade-Insecure-Requests":"1","User-Agent":"Mozilla/5.0 (Linux; Android 10; 16s Pro Build/QKQ1.191222.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.106 Mobile Safari/537.36  XiaoMi/MiuiBrowser/10.8.1 LT-APP/44/200","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9","x-app":"96c1ea5a-9a52-44c9-8ac4-8dceafa065c8","X-Requested-With":"com.quxianzhuan.wap","Sec-Fetch-Site":"none","Sec-Fetch-Mode":"navigate","Sec-Fetch-User":"?1","Sec-Fetch-Dest":"document","Referer":"https://wap.quxianzhuan.com/reward/list/?xapp-target=blank","Accept-Encoding":"gzip, deflate","Accept-Language":"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7","Cookie":"' +
				xqzck +
				'"}'
			),
			body: "reward_id=" + reward_id + "&formhash=" + formhash + "&inajax=1",
		};
		$.post(options, async (err, resp, data) => {
			try {
				const task = JSON.parse(data);
				if (task.state == 1) {
					console.log("\n闲趣赚任务：" + task.msg + "等待10秒继续下一任务");
					await $.wait(11000);
					await getNextTask();
				} else {
					console.log("\n闲趣赚任务：" + task.msg);
				}
			} catch (e) {
			} finally {
				resolve();
			}
		});
	});
}
function queryUser() {
	return new Promise(resolve => {
		let options = {
			url: "https://wap.quxianzhuan.com/user/",
			headers: JSON.parse(
				'{"Host":"wap.quxianzhuan.com","Connection":"keep-alive","Upgrade-Insecure-Requests":"1","User-Agent":"Mozilla/5.0 (Linux; Android 10; 16s Pro Build/QKQ1.191222.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.106 Mobile Safari/537.36  XiaoMi/MiuiBrowser/10.8.1 LT-APP/44/200","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9","x-app":"96c1ea5a-9a52-44c9-8ac4-8dceafa065c8","X-Requested-With":"com.quxianzhuan.wap","Sec-Fetch-Site":"none","Sec-Fetch-Mode":"navigate","Sec-Fetch-User":"?1","Sec-Fetch-Dest":"document","Referer":"https://wap.quxianzhuan.com/reward/list/?xapp-target=blank","Accept-Encoding":"gzip, deflate","Accept-Language":"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7","Cookie":"' +
				xqzck +
				'"}'
			),
		};
		$.get(options, async (err, resp, data) => {
			try {
				let money = data.match(/available_money":(.+?),"/)[1];
				let uid = data.match(/UID：(.+?)\<\/span\>/)[1];
				console.log(
					"\n闲趣赚靓仔用户：【" + uid + "】 - 可提现余额【" + money + "】"
				);
			} catch (e) {
			} finally {
				resolve();
			}
		});
	});
}

// prettier-ignore
function Env(t, s) {
	return new (class {
		constructor(t, s) {
			(this.name = t),
				(this.data = null),
				(this.dataFile = 'box.dat'),
				(this.logs = []),
				(this.logSeparator = '\n'),
				(this.startTime = new Date().getTime()),
				Object.assign(this, s),
				this.log('', `\ud83d\udd14${this.name}, \u5f00\u59cb!`);
		}
		isNode() {
			return 'undefined' != typeof module && !!module.exports;
		}
		isQuanX() {
			return 'undefined' != typeof $task;
		}
		isSurge() {
			return 'undefined' != typeof $httpClient && 'undefined' == typeof $loon;
		}
		isLoon() {
			return 'undefined' != typeof $loon;
		}
		getScript(t) {
			return new Promise((s) => {
				$.get({
					url: t
				}, (t, e, i) => s(i));
			});
		}
		runScript(t, s) {
			return new Promise((e) => {
				let i = this.getdata('@chavy_boxjs_userCfgs.httpapi');
				i = i ? i.replace(/\n/g, '').trim() : i;
				let o = this.getdata('@chavy_boxjs_userCfgs.httpapi_timeout');
				(o = o ? 1 * o : 20),
					(o = s && s.timeout ? s.timeout : o);
				const [h, a] = i.split('@'),
					r = {
						url: `http://${a}/v1/scripting/evaluate`,
						body: {
							script_text: t,
							mock_type: 'cron',
							timeout: o
						},
						headers: {
							'X-Key': h,
							Accept: '*/*'
						},
					};
				$.post(r, (t, s, i) => e(i));
			}).catch((t) => this.logErr(t));
		}
		loaddata() {
			if (!this.isNode())
				return {}; {
				(this.fs = this.fs ? this.fs : require('fs')),
					(this.path = this.path ? this.path : require('path'));
				const t = this.path.resolve(this.dataFile),
					s = this.path.resolve(process.cwd(), this.dataFile),
					e = this.fs.existsSync(t),
					i = !e && this.fs.existsSync(s);
				if (!e && !i)
					return {}; {
					const i = e ? t : s;
					try {
						return JSON.parse(this.fs.readFileSync(i));
					} catch (t) {
						return {};
					}
				}
			}
		}
		writedata() {
			if (this.isNode()) {
				(this.fs = this.fs ? this.fs : require('fs')),
					(this.path = this.path ? this.path : require('path'));
				const t = this.path.resolve(this.dataFile),
					s = this.path.resolve(process.cwd(), this.dataFile),
					e = this.fs.existsSync(t),
					i = !e && this.fs.existsSync(s),
					o = JSON.stringify(this.data);
				e ? this.fs.writeFileSync(t, o) : i ? this.fs.writeFileSync(s, o) : this.fs.writeFileSync(t, o);
			}
		}
		lodash_get(t, s, e) {
			const i = s.replace(/\[(\d+)\]/g, '.$1').split('.');
			let o = t;
			for (const t of i)
				if (((o = Object(o)[t]), void 0 === o))
					return e;
			return o;
		}
		lodash_set(t, s, e) {
			return Object(t) !== t ? t : (Array.isArray(s) || (s = s.toString().match(/[^.[\]]+/g) || []), (s.slice(0, -1).reduce((t, e, i) => (Object(t[e]) === t[e] ? t[e] : (t[e] = Math.abs(s[i + 1]) >> 0 == +s[i + 1] ? [] : {})), t)[s[s.length - 1]] = e), t);
		}
		getdata(t) {
			let s = this.getval(t);
			if (/^@/.test(t)) {
				const [, e, i] = /^@(.*?)\.(.*?)$/.exec(t),
					o = e ? this.getval(e) : '';
				if (o)
					try {
						const t = JSON.parse(o);
						s = t ? this.lodash_get(t, i, '') : s;
					} catch (t) {
						s = '';
					}
			}
			return s;
		}
		setdata(t, s) {
			let e = !1;
			if (/^@/.test(s)) {
				const [, i, o] = /^@(.*?)\.(.*?)$/.exec(s),
					h = this.getval(i),
					a = i ? ('null' === h ? null : h || '{}') : '{}';
				try {
					const s = JSON.parse(a);
					this.lodash_set(s, o, t),
						(e = this.setval(JSON.stringify(s), i));
				} catch (s) {
					const h = {};
					this.lodash_set(h, o, t),
						(e = this.setval(JSON.stringify(h), i));
				}
			} else
				e = $.setval(t, s);
			return e;
		}
		getval(t) {
			return this.isSurge() || this.isLoon() ? $persistentStore.read(t) : this.isQuanX() ? $prefs.valueForKey(t) : this.isNode() ? ((this.data = this.loaddata()), this.data[t]) : (this.data && this.data[t]) || null;
		}
		setval(t, s) {
			return this.isSurge() || this.isLoon() ? $persistentStore.write(t, s) : this.isQuanX() ? $prefs.setValueForKey(t, s) : this.isNode() ? ((this.data = this.loaddata()), (this.data[s] = t), this.writedata(), !0) : (this.data && this.data[s]) || null;
		}
		initGotEnv(t) {
			(this.got = this.got ? this.got : require('got')),
				(this.cktough = this.cktough ? this.cktough : require('tough-cookie')),
				(this.ckjar = this.ckjar ? this.ckjar : new this.cktough.CookieJar()),
				t && ((t.headers = t.headers ? t.headers : {}), void 0 === t.headers.Cookie && void 0 === t.cookieJar && (t.cookieJar = this.ckjar));
		}
		get(t, s = () => { }) {
			t.headers && (delete t.headers['Content-Type'], delete t.headers['Content-Length']),
				this.isSurge() || this.isLoon() ? $httpClient.get(t, (t, e, i) => {
					!t && e && ((e.body = i), (e.statusCode = e.status)),
						s(t, e, i);
				}) : this.isQuanX() ? $task.fetch(t).then((t) => {
					const {
						statusCode: e,
						statusCode: i,
						headers: o,
						body: h
					} = t;
					s(null, {
						status: e,
						statusCode: i,
						headers: o,
						body: h
					}, h);
				}, (t) => s(t)) : this.isNode() && (this.initGotEnv(t), this.got(t).on('redirect', (t, s) => {
					try {
						const e = t.headers['set-cookie'].map(this.cktough.Cookie.parse).toString();
						this.ckjar.setCookieSync(e, null),
							(s.cookieJar = this.ckjar);
					} catch (t) {
						this.logErr(t);
					}
				}).then((t) => {
					const {
						statusCode: e,
						statusCode: i,
						headers: o,
						body: h
					} = t;
					s(null, {
						status: e,
						statusCode: i,
						headers: o,
						body: h
					}, h);
				}, (t) => s(t)));
		}
		post(t, s = () => { }) {
			if ((t.body && t.headers && !t.headers['Content-Type'] && (t.headers['Content-Type'] = 'application/x-www-form-urlencoded'), delete t.headers['Content-Length'], this.isSurge() || this.isLoon()))
				$httpClient.post(t, (t, e, i) => {
					!t && e && ((e.body = i), (e.statusCode = e.status)),
						s(t, e, i);
				});
			else if (this.isQuanX())
				(t.method = 'POST'), $task.fetch(t).then((t) => {
					const {
						statusCode: e,
						statusCode: i,
						headers: o,
						body: h
					} = t;
					s(null, {
						status: e,
						statusCode: i,
						headers: o,
						body: h
					}, h);
				}, (t) => s(t));
			else if (this.isNode()) {
				this.initGotEnv(t);
				const {
					url: e,
					...i
				} = t;
				this.got.post(e, i).then((t) => {
					const {
						statusCode: e,
						statusCode: i,
						headers: o,
						body: h
					} = t;
					s(null, {
						status: e,
						statusCode: i,
						headers: o,
						body: h
					}, h);
				}, (t) => s(t));
			}
		}
		time(t) {
			let s = {
				'M+': new Date().getMonth() + 1,
				'd+': new Date().getDate(),
				'H+': new Date().getHours(),
				'm+': new Date().getMinutes(),
				's+': new Date().getSeconds(),
				'q+': Math.floor((new Date().getMonth() + 3) / 3),
				S: new Date().getMilliseconds(),
			};
			/(y+)/.test(t) && (t = t.replace(RegExp.$1, (new Date().getFullYear() + '').substr(4 - RegExp.$1.length)));
			for (let e in s)
				new RegExp('(' + e + ')').test(t) && (t = t.replace(RegExp.$1, 1 == RegExp.$1.length ? s[e] : ('00' + s[e]).substr(('' + s[e]).length)));
			return t;
		}
		msg(s = t, e = '', i = '', o) {
			const h = (t) => !t || (!this.isLoon() && this.isSurge()) ? t : 'string' == typeof t ? this.isLoon() ? t : this.isQuanX() ? {
				'open-url': t
			}
				: void 0 : 'object' == typeof t && (t['open-url'] || t['media-url']) ? this.isLoon() ? t['open-url'] : this.isQuanX() ? t : void 0 : void 0;
			$.isMute || (this.isSurge() || this.isLoon() ? $notification.post(s, e, i, h(o)) : this.isQuanX() && $notify(s, e, i, h(o))),
				this.logs.push('', '==============\ud83d\udce3\u7cfb\u7edf\u901a\u77e5\ud83d\udce3=============='),
				this.logs.push(s),
				e && this.logs.push(e),
				i && this.logs.push(i);
		}
		log(...t) {
			t.length > 0 ? (this.logs = [...this.logs, ...t]) : console.log(this.logs.join(this.logSeparator));
		}
		logErr(t, s) {
			const e = !this.isSurge() && !this.isQuanX() && !this.isLoon();
			e ? $.log('', `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t.stack) : $.log('', `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t);
		}
		wait(t) {
			return new Promise((s) => setTimeout(s, t));
		}
		done(t = {}) {
			const s = new Date().getTime(),
				e = (s - this.startTime) / 1e3;
			this.log('', `\ud83d\udd14${this.name}, \u7ed3\u675f! \ud83d\udd5b ${e} \u79d2`),
				this.log(),
				(this.isSurge() || this.isQuanX() || this.isLoon()) && $done(t);
		}
	})(t, s);
}

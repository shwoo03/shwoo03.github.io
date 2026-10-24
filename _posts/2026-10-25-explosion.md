---
title: "Explosion"
date: 2026-10-25 00:54:00 +0900
categories: ["Hack The Box", "Starting Point"]
tags: []
render_with_liquid: false
notion_id: "403eaafe-e12e-80c9-879d-fd13f8f0c1f9"
notion_url: "https://app.notion.com/p/Explosion-403eaafee12e80c9879dfd13f8f0c1f9"
notion_last_edited: "2026-10-24T16:21:00.000Z"
---

<div class="notion-page" markdown="1">

해당 문제는 HTB에서 공개 가능한 문제로 블로그에 라이트업 공개가 허용된 문제이므로 포스팅 합니다.

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### 개요
{: id="개요"}

Explosion은 <strong>매우 쉬운 Windows 머신</strong>으로, 다음 내용을 다룹니다.

- RDP(Remote Desktop Protocol, 원격 데스크톱 프로토콜)의 기본 개념
- <code>xfreerdp</code> 클라이언트를 사용해 RDP 서버에 접속하는 방법
- <strong>잘못된 보안 설정</strong>으로 인해 인증 없이 RDP에 접근할 수 있는 상황
{: .notion-bulleted-list-item}

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK1
{: id="task1"}

> What does the 3-letter acronym RDP stand for?

<code>Remote Desktop Protocol</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK2
{: id="task2"}

> What is a 3-letter acronym that refers to interaction with the host through a command line interface?

<code>CLI</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK3
{: id="task3"}

> What about graphical user interface interactions?

<code>GUI</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK4
{: id="task4"}

> What is the name of an old remote access tool that came without encryption by default and listens on TCP port 23?

<code>telnet</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK5
{: id="task5"}

> What is the name of the service running on port 3389 TCP?

```plaintext
nmap -T4 -sV -v 10.129.1.13 -p 3389
```

![image](/assets/img/notion/403eaafee12e80c9879dfd13f8f0c1f9/image.png){: w="630" h="95" }

<code>ms-wbt-server</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK6
{: id="task6"}

> What is the switch used to specify the target host&#x27;s IP address when using xfreerdp?

<code>/v:</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK7
{: id="task7"}

> What username successfully returns a desktop projection to us with a blank password?

```plaintext
xfreerdp /v:10.129.1.13 /u:Administrator /p:""
```

![image-2](/assets/img/notion/403eaafee12e80c9879dfd13f8f0c1f9/image-2.png){: w="1899" h="1253" }

<code>Administrator</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK8
{: id="task8"}

> Submit the flag located on the administrator&#x27;s desktop.

![image-3](/assets/img/notion/403eaafee12e80c9879dfd13f8f0c1f9/image-3.png){: w="434" h="161" }

<code>951fa96d7830c451b536be5a6be008a0</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

</div>

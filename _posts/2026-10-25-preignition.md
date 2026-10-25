---
title: "Preignition"
date: 2026-10-25 01:18:00 +0900
categories: ["Hack The Box", "Starting Point", "Tier 0 - Foundations"]
tags: []
render_with_liquid: false
notion_id: "403eaafe-e12e-80cc-bfc4-cc29242f0675"
notion_url: "https://app.notion.com/p/Preignition-403eaafee12e80ccbfc4cc29242f0675"
notion_last_edited: "2026-10-24T17:23:00.000Z"
---

<div class="notion-page" markdown="1">

해당 문제는 HTB에서 공개 가능한 문제로 블로그에 라이트업 공개가 허용된 문제이므로 포스팅 합니다.

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### 문제 개요
{: id="문제-개요"}

Preignition은 매우 쉬운 난이도의 Linux 머신으로, 웹 애플리케이션을 대상으로 한 기초적인 정보 수집(Enumeration)과 디렉터리 퍼징(Directory Fuzzing)을 다룹니다.

이 과정에서 취약한 관리자 로그인 페이지(Admin Login Endpoint)를 발견하게 되며, 이를 통해 잘못된 보안 설정과 기본 계정 정보(Default Credentials)를 그대로 사용하는 것이 얼마나 위험한지 보여줍니다.

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK1
{: id="task1"}

> Directory Brute-forcing is a technique used to check a lot of paths on a web server to find hidden pages. Which is another name for this? (i) Local File Inclusion, (ii) dir busting, (iii) hash cracking.

<code>dir busting</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK2
{: id="task2"}

> What switch do we use for nmap&#x27;s scan to specify that we want to perform version detection?

버전 탐지를 할 때는 -sV 옵션을 사용한다.

<code>-sV</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK3
{: id="task3"}

> What does Nmap report is the service identified as running on port 80/tcp?

```plaintext
nmap -p 80 10.129.58.186
```

포트 지정해서 스캔하면 다음 서비스가 나옴

![image](/assets/img/notion/403eaafee12e80ccbfc4cc29242f0675/image.png){: w="772" h="187" }

<code>http</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK4
{: id="task4"}

> What server name and version of service is running on port 80/tcp?

```plaintext
nmap -p 80 10.129.58.186 -sV
```

![image-2](/assets/img/notion/403eaafee12e80ccbfc4cc29242f0675/image-2.png){: w="805" h="186" }

<code>nginx 1.14.2</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK5
{: id="task5"}

> What switch do we use to specify to Gobuster we want to perform dir busting specifically?

dir 모드는 디렉터리 및 파일을 찾는 기능을 제공해준다.

<code>dir</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK6
{: id="task6"}

> When using gobuster to dir bust, what switch do we add to make sure it finds PHP pages?

\-x 옵션은 탐색할 파일의 확장자를 지정할 수 있게 해준다.

<code>-x php</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK7
{: id="task7"}

> What page is found during our dir busting activities?

![image-3](/assets/img/notion/403eaafee12e80ccbfc4cc29242f0675/image-3.png){: w="742" h="110" }

기본 워드리스트는 보통 HTB 머신이나 KALI 에서 /usr/share/wordlists/dirb 에 존재함

```plaintext
gobuster dir -u http://10.129.58.186 -x php -w /usr/share/wordlists/dirb/common.txt
```

![image-4](/assets/img/notion/403eaafee12e80ccbfc4cc29242f0675/image-4.png){: w="833" h="438" }

<code>admin.php</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK8
{: id="task8"}

> What is the HTTP status code reported by Gobuster for the discovered page?

<code>200</code>

<div class="notion-blank"></div>

<div class="notion-blank"></div>

### TASK9
{: id="task9"}

> Submit the flag located in the webpage.

```plaintext
http://10.129.58.186/admin.php
```

![image-5](/assets/img/notion/403eaafee12e80ccbfc4cc29242f0675/image-5.png){: w="873" h="204" }

로그인은 대충 admin/admin 하니까 나옴

<code>6483bee07c1c1d57f14e5b0717503c73</code>

<div class="notion-blank"></div>

</div>

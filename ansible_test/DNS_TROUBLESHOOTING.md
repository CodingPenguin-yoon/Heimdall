# GitLab DNS 및 리다이렉션 트러블슈팅 가이드

## 개요
이 문서는 GitLab의 `external_url` 설정과 DNS, 리다이렉션 관련 문제를 해결하는 방법을 정리한 것입니다.

**환경:**
- GitLab CE
- external_url: `http://yoongitlab.com`
- 서버 IP: `192.168.2.98`

---

## 문제: external_url과 DNS 설정의 관계

### 증상
- GitLab 서버에 IP 주소(`192.168.2.98`)로 접속하면 접속이 안 되거나 리다이렉트 오류 발생
- 도메인(`yoongitlab.com`)으로 접속하려고 하면 DNS 오류 발생

### 왜 이런 문제가 발생하는가?

#### 1. GitLab의 external_url 동작 원리

GitLab의 `external_url` 설정은 다음과 같이 동작합니다:

```
1. 사용자가 브라우저로 접속
   ↓
2. GitLab 서버가 요청을 받음
   ↓
3. GitLab이 external_url을 확인
   ↓
4. external_url과 요청 URL이 다르면 리다이렉트
   ↓
5. 리다이렉트된 URL로 다시 접속 시도
```

**예시:**
- `external_url = "http://yoongitlab.com"`로 설정
- 사용자가 `http://192.168.2.98`로 접속
- GitLab: "설정된 URL은 `yoongitlab.com`인데, 요청은 `192.168.2.98`이네?"
- GitLab: `http://yoongitlab.com`으로 리다이렉트
- 브라우저: `yoongitlab.com`을 DNS로 조회 → 실패 (DNS 설정 없음)
- 결과: 접속 불가

#### 2. 네트워크 레벨에서의 동작

```
[클라이언트 PC]                    [GitLab 서버]
     |                                   |
     | 1. HTTP GET http://192.168.2.98   |
     |---------------------------------->|
     |                                   |
     | 2. external_url 확인              |
     |    "http://yoongitlab.com"        |
     |                                   |
     | 3. HTTP 302 Redirect              |
     |    Location: http://yoongitlab.com|
     |<----------------------------------|
     |                                   |
     | 4. DNS 조회: yoongitlab.com       |
     |    → 실패 (DNS 설정 없음)          |
     |                                   |
     | 5. 접속 실패                      |
```

---

## 해결 방법

### 방법 1: IP 주소로 external_url 설정 (간단, 권장하지 않음)

**설정:**
```yaml
# deploy_gitlab_server.yml
vars:
  gitlab_external_url: "http://192.168.2.98"
```

**장점:**
- DNS 설정 불필요
- 즉시 접속 가능

**단점:**
- GitLab이 생성하는 모든 URL이 IP 주소로 생성됨
  - 클론 URL: `git clone http://192.168.2.98/...`
  - 웹훅 URL: `http://192.168.2.98/api/v4/...`
  - 이메일 링크: `http://192.168.2.98/...`
- 나중에 도메인으로 변경하려면 모든 설정을 다시 해야 함

**언제 사용:**
- 테스트 환경
- 임시 설치
- 도메인을 사용할 계획이 없는 경우

---

### 방법 2: 도메인으로 external_url 설정 + 클라이언트 DNS 설정 (권장)

#### 2-1. GitLab 서버 설정

**설정:**
```yaml
# deploy_gitlab_server.yml
vars:
  gitlab_external_url: "http://yoongitlab.com"
```

**중요:** GitLab 서버 자체에는 DNS 설정이 **필요 없습니다**.
- GitLab 서버는 `external_url` 설정만 있으면 됨
- 서버가 DNS를 조회하지 않음
- 서버는 단순히 설정된 URL을 응답에 사용할 뿐

#### 2-2. 클라이언트 PC DNS 설정

**macOS/Linux:**
```bash
# /etc/hosts 파일에 추가
sudo echo "192.168.2.98 yoongitlab.com" >> /etc/hosts

# 확인
cat /etc/hosts | grep yoongitlab
```

**Windows:**
```
# C:\Windows\System32\drivers\etc\hosts 파일에 추가
192.168.2.98 yoongitlab.com
```

**동작 원리:**
```
[클라이언트 PC]                    [GitLab 서버]
     |                                   |
     | 1. 브라우저: yoongitlab.com 입력  |
     |                                   |
     | 2. /etc/hosts 확인                |
     |    → 192.168.2.98로 변환          |
     |                                   |
     | 3. HTTP GET http://192.168.2.98   |
     |    Host: yoongitlab.com            |
     |---------------------------------->|
     |                                   |
     | 4. GitLab: external_url 확인      |
     |    "http://yoongitlab.com"        |
     |    Host 헤더: "yoongitlab.com"    |
     |    → 일치! 리다이렉트 없음        |
     |                                   |
     | 5. HTTP 200 OK                    |
     |<----------------------------------|
     |                                   |
     | 6. 정상 접속                      |
```

**장점:**
- GitLab이 생성하는 모든 URL이 도메인으로 생성됨
- 클론 URL: `git clone http://yoongitlab.com/...`
- 웹훅 URL: `http://yoongitlab.com/api/v4/...`
- 나중에 실제 DNS 서버 설정 시 변경 없이 사용 가능

**단점:**
- 각 클라이언트 PC마다 `/etc/hosts` 설정 필요
- 여러 PC에서 사용하려면 각각 설정해야 함

---

### 방법 3: 네트워크 DNS 서버 설정 (프로덕션 권장)

**설정:**
1. 네트워크의 DNS 서버에 A 레코드 추가
   ```
   yoongitlab.com  A  192.168.2.98
   ```

2. 클라이언트 PC의 DNS 서버를 네트워크 DNS로 설정

**장점:**
- 모든 클라이언트에서 자동으로 도메인 해석
- `/etc/hosts` 설정 불필요
- 중앙 관리 가능

**단점:**
- DNS 서버 접근 권한 필요
- 네트워크 인프라 설정 필요

---

## 왜 클라이언트 DNS만으로는 안 되는가?

### 질문: "서버에 DNS 설정 안 하고 클라이언트에만 설정하면 안 되나?"

**답변: 안 됩니다. 이유는 다음과 같습니다:**

#### 시나리오 1: external_url을 IP로 설정 + 클라이언트에 도메인 DNS 설정

```
설정:
- GitLab 서버: external_url = "http://192.168.2.98"
- 클라이언트 PC: /etc/hosts에 "192.168.2.98 yoongitlab.com" 추가

동작:
1. 클라이언트가 http://yoongitlab.com으로 접속
2. /etc/hosts로 192.168.2.98로 변환
3. HTTP 요청: GET http://192.168.2.98 (Host: yoongitlab.com)
4. GitLab 서버가 요청 받음
5. GitLab: "external_url은 192.168.2.98인데, Host 헤더는 yoongitlab.com이네?"
6. GitLab: 리다이렉트 없이 처리 (일부 경우)
7. 하지만 GitLab이 생성하는 URL은 여전히 IP 주소
   - 클론 URL: http://192.168.2.98/...
   - 웹훅 URL: http://192.168.2.98/api/v4/...
```

**결과:**
- 접속은 가능하지만, GitLab이 제공하는 모든 URL이 IP 주소로 생성됨
- 도메인의 이점을 활용할 수 없음

#### 시나리오 2: external_url을 도메인으로 설정 + 클라이언트에 도메인 DNS 설정 (올바른 방법)

```
설정:
- GitLab 서버: external_url = "http://yoongitlab.com"
- 클라이언트 PC: /etc/hosts에 "192.168.2.98 yoongitlab.com" 추가

동작:
1. 클라이언트가 http://yoongitlab.com으로 접속
2. /etc/hosts로 192.168.2.98로 변환
3. HTTP 요청: GET http://192.168.2.98 (Host: yoongitlab.com)
4. GitLab 서버가 요청 받음
5. GitLab: "external_url은 yoongitlab.com이고, Host 헤더도 yoongitlab.com이네?"
6. GitLab: 일치! 정상 처리
7. GitLab이 생성하는 모든 URL이 도메인으로 생성됨
   - 클론 URL: http://yoongitlab.com/...
   - 웹훅 URL: http://yoongitlab.com/api/v4/...
```

**결과:**
- 접속 가능
- 모든 URL이 도메인으로 생성됨
- 나중에 실제 DNS 서버 설정 시 변경 없이 사용 가능

---

## HTTP Host 헤더와 리다이렉션

### HTTP 요청 구조

```
GET / HTTP/1.1
Host: yoongitlab.com          ← 클라이언트가 보내는 헤더
User-Agent: Mozilla/5.0...
Accept: text/html...
```

### GitLab의 리다이렉션 로직

```ruby
# GitLab 내부 로직 (의사코드)
if request.host != external_url.host
  redirect_to external_url
end
```

**예시:**
- `external_url = "http://yoongitlab.com"`
- 요청 Host 헤더: `192.168.2.98`
- 결과: `http://yoongitlab.com`으로 리다이렉트

---

## 실제 문제 해결 사례

### 문제: IP로 접속했는데 리다이렉트 오류

**증상:**
```bash
$ curl -I http://192.168.2.98
HTTP/1.1 302 Found
Location: http://yoongitlab.com/users/sign_in
```

**원인:**
- `external_url = "http://yoongitlab.com"`로 설정됨
- IP로 접속하면 GitLab이 도메인으로 리다이렉트
- DNS 설정 없어서 접속 실패

**해결:**
1. 클라이언트 PC의 `/etc/hosts`에 추가:
   ```bash
   echo "192.168.2.98 yoongitlab.com" | sudo tee -a /etc/hosts
   ```

2. 도메인으로 접속:
   ```bash
   curl -I http://yoongitlab.com
   HTTP/1.1 200 OK
   ```

---

## 요약

### 핵심 원칙

1. **GitLab 서버에는 DNS 설정 불필요**
   - `external_url` 설정만 있으면 됨
   - 서버는 DNS를 조회하지 않음

2. **클라이언트에는 DNS 설정 필요**
   - 도메인으로 접속하려면 클라이언트 PC에 DNS 설정 필요
   - `/etc/hosts` 또는 네트워크 DNS 서버 사용

3. **external_url과 접속 URL은 일치해야 함**
   - `external_url = "http://yoongitlab.com"`이면
   - 클라이언트도 `http://yoongitlab.com`으로 접속해야 함
   - IP로 접속하면 리다이렉트 발생

### 권장 설정

**개발/테스트 환경:**
- `external_url = "http://yoongitlab.com"`
- 클라이언트 PC: `/etc/hosts` 설정

**프로덕션 환경:**
- `external_url = "http://yoongitlab.com"`
- 네트워크 DNS 서버에 A 레코드 설정

---

## 참고 자료

- [GitLab external_url 문서](https://docs.gitlab.com/omnibus/settings/configuration.html#configuring-the-external-url-for-gitlab)
- [HTTP Host 헤더 설명](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Host)
- [DNS A 레코드 설정](https://www.cloudflare.com/learning/dns/dns-records/dns-a-record/)


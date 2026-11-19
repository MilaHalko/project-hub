# Login brute-force protection

Date: 2026-11-19
Status: approved scope (mentor review, approved by Mila); storage choice is the builder's call
Builds on: [users and auth design](2026-11-13-users-auth-design.md), where this was postponed

## Intent

The mentor sent 12 wrong passwords to `POST /login` in a row and every one got `401` at
full speed. An attacker can guess passwords without limit. After a few failures the API must
refuse further attempts for a while.

## The rule in two sentences

Every login attempt is counted against the submitted login and against the client IP before
the password is checked. Once a login has had 5 failures in 15 minutes (or an IP 20), further
attempts get `429` with `Retry-After`, even with the right password, until the oldest failure
leaves the window; a successful login erases that login's count.

## Goals

- 5 failures per login in 15 minutes, 20 per client IP in 15 minutes (settings
  `login_max_failures`, `login_ip_max_failures`, `login_window_seconds`).
- `429`, `Retry-After` in whole seconds, body `{"detail": "..."}` like every other error.
- Unknown logins are counted too, so a `429` does not reveal which logins exist.
- A success resets that login's counter, not the IP's.
- Failed and blocked attempts go to the security events log: the masked login (`mi***`) and
  the client IP, never a password.

## Non-goals

- Protection that survives a restart or covers several tasks (see storage).
- CAPTCHAs, progressive delays, protection of other endpoints.

## Constraints and findings

- Client IP: uvicorn runs with `--proxy-headers --forwarded-allow-ips=127.0.0.1`. The only
  proxy that talks to the API is nginx in the same ECS task (127.0.0.1); the ALB appends the
  real client address to `X-Forwarded-For` and nginx passes the header through. uvicorn
  accepts the header only from 127.0.0.1 and takes the rightmost address, the one the ALB
  added, so a forged leftmost value changes nothing and a request that reaches the API
  directly keeps its socket address. `request.client.host` is therefore the key.
- The flags are written out in the `Dockerfile` because uvicorn also reads the
  `FORWARDED_ALLOW_IPS` environment variable, and a `*` there would trust anyone.
- Known trade-off (already recorded in the auth design): an attacker can lock someone's login
  for up to 15 minutes. The login limit is low on purpose; the per-IP limit is higher so one
  office behind one address is not locked out by a few typos.

## Approaches

| Option | Works across tasks | Costs | Verdict |
| --- | --- | --- | --- |
| In-memory counters in the API process | No: each task counts alone, a restart forgets | One small class, no schema | **Chosen** |
| `login_attempts` table | Yes | Migration, ORM and SQL repositories, contract tests, a cleanup job | Right when the service runs several tasks |
| Rate rule on the load balancer or WAF | Yes | A WAF is billed; it limits per IP, not per login | Not chosen |

Why in-memory: the ECS service runs `desired_count = 1`, so one process sees every request
and the counters are correct. The limit is `N x tasks` if the service is scaled out and the
counters reset on deploy; the table is the upgrade then.

## What is left to the builder

Counting before checking the password, so parallel guesses cannot all pass the check while
the first hash is still running; sweeping expired keys so random logins cannot grow memory
without bound.

# Kubernetes Liveness, Readiness and Startup Probes: Restart or Stop Traffic?

A container can be "running" and still be useless. The process may be deadlocked, still loading a cache, or waiting on a database that's gone away. Kubernetes can't see any of that by itself, so it asks your app through **probes**. Each kind of probe triggers a different action when it fails. If you mix them up, you get one of two outages: a broken pod that keeps receiving traffic, or a whole fleet of healthy pods restarting together because a dependency had a short glitch.

After reading this you will be able to:

- say exactly what happens when each probe type fails,
- read and tune the timing fields in a probe spec and work out how long detection takes,
- decide which checks belong in liveness and which belong in readiness,
- watch a pod leave and rejoin a Service's endpoints without restarting.

## The concept

The **kubelet** is the agent on each node that runs your containers. It also runs the probes. A probe is a small check, here an HTTP GET, that the kubelet repeats on a schedule. A response code from 200 to 399 counts as success. Any other code, a timeout or a refused connection counts as failure. When failures in a row reach `failureThreshold`, the probe is considered failed, and the result depends on which probe it is:

| Probe       | Question it answers                    | On failure                                               |
|-------------|----------------------------------------|----------------------------------------------------------|
| `startupProbe`   | "Has the app finished booting?"   | Container is killed and restarted (per `restartPolicy`)  |
| `livenessProbe`  | "Is the process still healthy?"   | Container is killed and restarted                        |
| `readinessProbe` | "Should this pod get traffic now?"| Pod is marked NotReady and **removed from Service endpoints**. No restart |

While the startup probe has not yet succeeded, the kubelet does **not** run liveness or readiness. After it succeeds once, it stops running and the other two take over for the rest of the container's life.

```
container starts
      │
      ▼
┌──────────────┐  fail ×30   ┌─────────┐
│ startupProbe │────────────▶│ restart │
└──────┬───────┘             └─────────┘
       │ first success
       ▼
┌───────────────┐  fail ×3   ┌─────────┐
│ livenessProbe │───────────▶│ restart │      (runs forever, in parallel)
└───────────────┘            └─────────┘
┌────────────────┐ fail ×3   ┌──────────────────────────────┐
│ readinessProbe │──────────▶│ Ready=False, IP removed from │
└────────────────┘           │ Endpoints; success re-adds it│
                             └──────────────────────────────┘
```

Readiness can be undone. When the probe passes again, the pod's IP goes back into the Service. A liveness restart can't be undone: in-memory state is lost, and the app pays its boot cost again.

**Cost and timing.** Each probe is one HTTP request per `periodSeconds` per container, so the overhead is constant and small. What matters is how quickly a failure gets detected, which is roughly `periodSeconds × failureThreshold`:

- shorter periods and lower thresholds mean faster detection but more false positives under load,
- longer periods and higher thresholds mean fewer false positives but more time spent sending traffic to a broken pod, or keeping a hung process alive.

**The key design rule:** liveness should check *only the process itself*. Suppose liveness checks the database and the database has a 30-second blip. Every replica's liveness check fails at the same moment and every replica restarts at once. A restart doesn't fix the database, so you've turned a dependency problem into a full outage. Put dependency checks in readiness instead. Pods then stop taking traffic while the dependency is down and come back automatically, with nothing restarted.

## Walking through the code

The whole lesson is one manifest, [`pod.yaml`](pod.yaml). We'll go through it top to bottom.

```yaml
apiVersion: v1
kind: Pod
```

`Pod` is in the core API group, so `apiVersion` is just `v1`. In production you'd usually put this spec inside a Deployment's pod template. The probe fields are the same in both places.

```yaml
metadata:
  name: web
  labels: {app: web}
```

`name: web` is how you refer to the pod with `kubectl`. The label `app: web` is written in YAML flow style (`{key: value}`), which means the same as the block form. It matters because a Service picks its pods with a label selector. Readiness only affects traffic for Services that select this pod, so without a label there's nothing for readiness to remove the pod from.

```yaml
spec:
  containers:
  - name: web
    image: my-app:1.0
```

This is a single container. `my-app:1.0` is a placeholder for your own image. The probes below assume it runs an HTTP server on port 8080 with `/healthz` and `/ready` endpoints. Probes are set **per container**, not per pod.

```yaml
    startupProbe:
      httpGet: {path: /healthz, port: 8080}
      failureThreshold: 30
      periodSeconds: 10
```

The kubelet sends `GET /healthz` on port 8080 to the pod IP every 10 seconds. It allows up to 30 failures in a row before it gives up, which gives a boot budget of 30 × 10 = **300 seconds**. A slow app (JVM warm-up, migrations, cache loading) gets five minutes to come up, and the liveness probe doesn't have to be made less sensitive to allow for that. The startup probe uses the same `/healthz` endpoint as liveness on purpose. Its job is to answer "is the process alive yet?", and then it hands that same question to liveness.

```yaml
    livenessProbe:
      httpGet: {path: /healthz, port: 8080}
      periodSeconds: 10
      failureThreshold: 3
```

After startup succeeds, liveness checks `/healthz` every 10 seconds. Three failures in a row (about 30 seconds) make the kubelet kill and restart the container, and the pod's `RESTARTS` count goes up. `/healthz` should be cheap and depend only on the process: "my event loop answers", not "my database answers". Fields that aren't set use their defaults: `timeoutSeconds: 1`, `successThreshold: 1`, `initialDelaySeconds: 0`.

```yaml
    readinessProbe:
      httpGet: {path: /ready, port: 8080}
      periodSeconds: 5
```

Readiness uses a **different endpoint**, `/ready`, and that's where dependency checks go: DB connection, downstream services, warm caches. It runs more often (every 5 seconds) because putting a pod back into rotation quickly is cheap and safe. `failureThreshold` uses its default of 3, so the pod is marked NotReady after about 15 seconds of failures and its IP is removed from the Endpoints of every matching Service. The container isn't touched and the restart count stays the same.

## Run it yourself

Prerequisites: `kubectl` and access to a Kubernetes cluster (a local one such as kind or minikube is enough). You also need an image to replace `my-app:1.0` that serves `/healthz` and `/ready` on port 8080, with a way to make `/ready` fail.

```sh
kubectl apply -f pod.yaml
kubectl expose pod web --port=8080
kubectl get pod web
kubectl get endpoints web
kubectl describe pod web
```

`kubectl expose pod web` creates a Service named `web` whose selector is copied from the pod's labels (`app=web`). That gives readiness an endpoint list to add the pod to and remove it from.

There is no recorded terminal output for this example, so here is what to look for instead of a transcript:

1. **During boot**, `kubectl get pod web` shows `READY 0/1`. The startup probe is still failing (within its 300-second budget) and readiness hasn't started yet. `kubectl get endpoints web` shows no addresses.
2. **After `/healthz` and `/ready` both succeed**, the pod shows `READY 1/1` and the endpoints list includes the pod's IP on port 8080.
3. **Make `/ready` fail.** About 15 seconds later (3 × 5 s), `READY` drops to `0/1` and the pod IP is no longer in `kubectl get endpoints web`. `RESTARTS` **stays at 0**, because readiness never restarts anything. `kubectl describe pod web` shows `Readiness probe failed` events.
4. **Make `/ready` succeed again.** The IP comes back on the next passing probe (`successThreshold` is 1).
5. If you made `/healthz` fail instead, about 30 seconds later the events would show `Liveness probe failed` followed by a kill and restart, and `RESTARTS` would go up.

## Try it

1. **Shrink the startup budget.** Set the startup `failureThreshold: 2` and use an app that takes 60 seconds to boot. Prediction: the container is killed after about 20 seconds, restarts, and ends up in `CrashLoopBackOff`. This shows why slow apps need a startup probe.
2. **Remove the startup probe entirely** and keep liveness as it is. Same slow app. Prediction: liveness starts at once, fails three times in about 30 seconds and restarts the container before it finishes booting. That's the problem the startup probe solves.
3. **Point liveness at `/ready`.** Then break the dependency that `/ready` checks. Prediction: instead of just leaving the Service, the pod gets restarted over and over. Scale up to 3 replicas and they all restart together. This is the classic mistake, reproduced on purpose.
4. **Tune readiness speed.** Change readiness to `periodSeconds: 1, failureThreshold: 1`. Prediction: the pod leaves endpoints almost immediately, and also flaps whenever one request is slow. You'll see that fast detection and stability pull against each other.
5. **Add `timeoutSeconds`.** Make `/healthz` respond in 2 seconds. With the default `timeoutSeconds: 1`, every check counts as a failure. Set `timeoutSeconds: 3` and watch the failures stop.

## Common pitfalls

- **Dependency checks in liveness.** One database blip restarts every replica at once. Keep liveness about the process; put dependencies in readiness.
- **Overly aggressive probes.** A low `timeoutSeconds` or `failureThreshold` on a busy service causes restarts under load. Each restart moves more load onto the remaining pods, which then fail their probes too. The result is a restart loop.
- **Using `initialDelaySeconds` instead of a startup probe.** A fixed delay is either too short (restarts) or too long (slow recovery after real hangs). A startup probe adapts: it ends as soon as the app is up.
- **Expecting readiness to restart a stuck pod.** It won't. A pod can stay NotReady indefinitely. If the process is truly wedged, liveness has to catch it.
- **No Service selecting the pod.** Readiness still changes the `READY` column, but no traffic is affected because no Endpoints list includes the pod.
- **Expensive health endpoints.** Probes run on every replica, every period, so a check that runs a heavy query adds real load.

**Interview follow-ups:**

- *One-line answer:* "Liveness restarts, readiness removes from traffic, startup protects slow boots."
- *How long until a hung container is restarted here?* About `10 s × 3 = 30 s` after the startup probe has passed, plus up to `timeoutSeconds` per check.
- *What other probe mechanisms exist besides `httpGet`?* `tcpSocket`, `exec` (a command's exit code) and `grpc`.
- *Why do rolling updates depend on readiness?* A Deployment counts a new pod as available only when it's Ready. With no readiness probe, the pod is Ready as soon as it starts, so traffic can reach it before it can serve.

## Further reading

- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Pod Lifecycle: Container probes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes)
- [Liveness, Readiness, and Startup Probes (concepts)](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/)

<!-- studio-job: kubernetes-liveness-vs-readiness-vs-startup-probes-what-each -->

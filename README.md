### Install/Run

```bash
$ git clone https://github.com/shadowban-eu/shadowban-testing ./shadowban-testing; cd $_
$ ./docker-entry.sh .env.example # takes any .env file
```

### Memory Profiling
Using [memory-profiler](https://pypi.org/project/memory-profiler/) to debug memory usage:

```bash
# When env vars are already set
$ ./docker-entry.sh mprof
# Otherwise, read from file
$ ./docker-entry.sh .env.example mprof
# Passes remaining arguments to mprof (set interval to 5s)
$ ./docker-entry.sh .env.example mprof -T 5
```

### Docker

Follow the quickstart instructions in our docker repo's [README](https://github.com/shadowban-eu/docker#shadowbandev).

### Install/Run

```bash
$ git clone https://github.com/shadowban-eu/testing ./testing; cd $_
$ ./bin/install.sh
$ ./bin/docker-entry.sh .env.example # takes any .env file
```

### Memory Profiling
Using [memory-profiler](https://pypi.org/project/memory-profiler/) to debug memory usage:

```bash
# When env vars are already set
$ ./bin/docker-entry.sh mprof
# Otherwise, read from file
$ ./bin/docker-entry.sh .env.example mprof
# Passes remaining arguments to mprof (set interval to 5s)
$ ./bin/docker-entry.sh .env.example mprof -T 5
```

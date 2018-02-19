import simpy
import random

L1HitRate = 0.5
L2HitRate = 0.8
LoadStoreCmd = ['ldr', 'str']
num_msq = 10
num_orq = 32
L2LatMin = 8
L2LatMax = 120




def toss(success_rate):
    return random.uniform(0, 1) < success_rate


class Pool(object):
    def __init__(self):
        self.id = 0

    def draw(self):
        id = self.id
        self.id = self.id+1
        return id

class L2Ctrl(object):
    def __init__(self, env, orq_capacity, pool):
        self.env = env
        self.pool = pool
        self.orq_arbiter = simpy.Resource(env, orq_capacity)
        self.orq_freelist = list(range(0, orq_capacity))
        self.orq_packets = [None] * orq_capacity

    def alloc_orq(self, packet):
        assert self.orq_freelist
        orq_id = self.orq_freelist.pop()
        self.orq_packets[orq_id] = packet
        return orq_id

    def release_orq(self, orq_id):
        assert not orq_id in self.orq_freelist
        self.orq_freelist.append(orq_id)

    def access(self, orq_id):
        hit_L2Cache = toss(L2HitRate)
        packet = self.orq_packets[orq_id]
        execstr = "ORQ(%d)-Addr(%08x)#" % (orq_id, packet.get_addr())
        lat = random.randint(L2LatMin, L2LatMax)
        start = self.env.now
        yield self.env.timeout(lat)
        end = start + lat
        execstr += "[%d" % start
        execstr += "-" * lat
        execstr += "%d]." % end
        return 0, execstr


class MSQ(object):
    def __init__(self, env, capacity, L2, pool):
        self.env = env
        self.arbiter = simpy.Resource(env, capacity)
        self.free_list = list(range(0, capacity))
        self.pool = pool
        self.L2 = L2
        self.packets = [None] * capacity

    def alloc(self, packet):
        assert self.free_list
        msq_id = self.free_list.pop()
        self.packets[msq_id] = packet
        return msq_id

    def release(self, msq_id):
        assert not msq_id in self.free_list
        self.free_list.append(msq_id)
        return msq_id

    def access(self, msq_id):

        req = self.packets[msq_id]
        execstr = ''
        with self.L2.orq_arbiter.request() as request:
            yield request
            # alloc a orq
            orq_id = self.L2.alloc_orq(req)
            L2_access = self.env.process(self.L2.access(orq_id))
            code, L2_execstr = yield L2_access
            execstr += "MSQ(%d) %s" % (msq_id, L2_execstr)
            # release the orq
            self.L2.release_orq(orq_id)
            return (code, execstr)

class Packet(object):
    def __init__(self, pool):
        self.cmd = None
        self.addr = None
        self.id = pool.draw()

    def get_id(self):
        return self.id

    def rand_addr(self, start_addr, end_addr):
        self.addr = random.randint(start_addr, end_addr)

    def rand_cmd(self, cmd_list):
        self.cmd = random.choice(cmd_list)

    def get_addr(self):
        return self.addr

    def get_cmd(self):
        return self.cmd


class LoadStore(object):
    def __init__(self, env, L2, pool):
        self.env = env
        self.msq = MSQ(env, num_msq, L2, pool)
        self.pool = pool

    def do(self, packet):
        cmd = packet.get_cmd()
        if cmd == 'ldr':
            yield self.env.process(self.load(packet))
        elif cmd == 'str':
            yield self.env.process(self.store(packet))

    def store(self, packet):
        id = packet.get_id()
        addr = packet.get_addr()
        execstr = "@%6d str::id=%d ::addr=%05x" % (env.now, id, addr)
        lat = 1
        execstr += "[%d]." % lat
        yield self.env.timeout(lat)
        print("%s" % execstr)

    def load(self, packet):
        id = packet.get_id()
        addr = packet.get_addr()
        execstr = "@%6d ldr::id=%d ::addr=%05x-" % (env.now, id, addr)
        lat = 1
        execstr += "[%d]." % lat
        data_arrival = self.env.process(self.accessL1(id, packet))
        code, L1_execstr = yield data_arrival
        execstr += L1_execstr
        print("%s" % execstr)

    def accessL1(self, id, packet):
        prob = random.uniform(0, 1)
        hit_L1Cache = toss(L1HitRate)
        id = self.pool.draw()
        execstr = "L1#%d" % id

        if hit_L1Cache:
            lat = random.randint(2, 3)  # L1 latency
            execstr += "[%d]." % lat
            yield self.env.timeout(lat)
            return 0, execstr
        else:  # miss L1
            lat = 2
            execstr += "[%d]." % lat
            # wait for msq request grant
            with self.msq.arbiter.request() as request:
                yield request
                # alloc a msq
                msq_id = self.msq.alloc(packet)
                #print('@%d: msq req grant %d' % (self.env.now, msq_id))
                msq_access = self.env.process(self.msq.access(msq_id))
                code, L2_execstr = yield msq_access
                execstr += "%s" % L2_execstr
                # release the msq
                self.msq.release(msq_id)
                return (code, execstr)

from simpy.events import AnyOf, AllOf, Event


def setup(env, pool, loadstore, num_transactions):
    start = env.now
    threads = [None]*num_transactions
    for i in range(num_transactions):
        packet = Packet(pool)
        packet.rand_addr(100, 500)
        packet.rand_cmd(LoadStoreCmd)
        yield env.timeout(random.randint(1, 2))
        #yield env.timeout(1)
        threads[i] = env.process(loadstore.do(packet))
        i += 1

    # wait for all thread to terminate
    finish = AllOf(env, threads)
    yield finish
    # make sure all finished
    assert all(e.processed for e in threads)
    end = env.now
    eclipse = end - start
    throughput = num_transactions / eclipse
    print("###################################################")
    print("Total %d transactions finish at time=%d" % (num_transactions, env.now))
    print("Throughput = %f transactions per cycle" % throughput)
    print("###################################################")
    return


def monitor(env, msq, msq_status, L2, orq_status):
    i = 0
    while True:
        msq_status[i] = num_msq - len(msq.free_list)
        orq_status[i] = num_orq - len(L2.orq_freelist)
        yield env.timeout(1)
        i += 1


import memory
env = simpy.Environment()
mem = memory.Memory(256, 1024)
mem.linearize()
print("mem has data %s" % mem.data)
mem.write(512, 89)
pool = Pool()
L2 = L2Ctrl(env, num_orq, pool)

sim_cycles = 5000


num_ls = 2
ls = [None] * num_ls
ls_msq_status = [None] * num_ls
for i in range(0, num_ls):
    ls[i] = LoadStore(env, L2, pool)
    ls_msq_status[i] = [None] * sim_cycles


orq_status = [None] * sim_cycles
print('start running')

#loadstore0
# create a monitor thread
for i in range(0, num_ls):
    env.process(monitor(env, ls[i].msq, ls_msq_status[i], L2, orq_status))
    # run the main simulation
    env.process(setup(env, pool, ls[i], 1000))


env.run(until=sim_cycles)

# plot the utilization
import pylab as pl
x = range(1, sim_cycles+1)
msq_limit = [num_msq] * sim_cycles
orq_limit = [num_orq] * sim_cycles

for i in range(0, num_ls):
    pl.plot(x, ls_msq_status[i])
pl.plot(x, orq_status)
pl.plot(x, msq_limit)
pl.plot(x, orq_limit)

pl.show()

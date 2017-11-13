import simpy
import random


class Memory(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.data = []

    def length(self):
        return self.end - self.start +1

    def linearize(self):
        for i in range(self.start, self.end+1):
            self.data.append(i)

    def rand(self):
        for i in range(0, self.length()):
            self.data.append(random.randint(0,100))

    def check(self,addr):
        assert addr>=self.start and addr<=self.end


    def read(self,addr):
        self.check(addr)
        return self.data[addr-self.start]

    def write(self, addr, data):
        self.check(addr)
        self.data[addr-self.start] = data


class Pool(object):
    def __init__(self):
        self.id = 0

    def draw(self):
        id = self.id
        self.id = self.id+1
        return id


class MSQ(object):
    def __init__(self, env, num_units, pool):
        self.env = env
        self.arbiter = simpy.Resource(env, num_units)
        #self.free_array = [1] * num_units  #0..num_units-1
        #self.busy_array = [0] * num_units
        self.free_list = list(range(0, num_units))
        self.pool = pool

    def alloc(self):
        assert self.free_list
        msq_id = self.free_list.pop()
        return msq_id

    def release(self, msq_id):
        assert not msq_id in self.free_list
        self.free_list.append(msq_id)
        return msq_id

    def access(self, msqid):
        hitL2 = random.uniform(0, 1) < 0.75
        execstr = "MSQ(%d)#" % msqid
        lat = random.randint(8, 40)
        start = self.env.now
        yield self.env.timeout(lat)
        end = start + lat
        execstr += "[%d" % start
        execstr += "-" * lat
        execstr += "%d]." % end
        return 0, execstr


class LoadStore(object):
    def __init__(self, env, msq, pool):
        self.env = env
        self.msq = msq
        self.pool = pool

    def load(self):
        print('@{0:5d} : '.format(self.env.now), end='')
        id = self.pool.draw()
        execstr = "ldr#%d" % id
        lat = 1
        execstr += "[%d]." % lat
        data_arrival = self.env.process(self.accessL1(id))
        code, L1_execstr = yield data_arrival
        execstr += L1_execstr
        print("%s" % execstr)

    def accessL1(self, id):
        prob = random.uniform(0, 1)
        hitL1 = prob < 0.5
        id = self.pool.draw()
        execstr = "L1#%d" % id

        if hitL1:
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
                msq_id = self.msq.alloc()
                #print('@%d: msq req grant %d' % (self.env.now, msq_id))
                L2 = self.env.process(self.msq.access(msq_id))
                code, L2_execstr = yield L2
                execstr += "%s" % L2_execstr
                # release the msq
                self.msq.release(msq_id)
                return (code, execstr)


def setup(env, loadstore, num_transactions):
    for i in range(num_transactions):
        yield env.timeout(random.randint(0,2))
        env.process(loadstore.load())
        i += 1


env = simpy.Environment()
mem = Memory(256, 1024)
mem.linearize()
print("mem has data %s" % mem.data)
mem.write(512, 89)
pool = Pool()
msq = MSQ(env, 4, pool)
ls = LoadStore(env, msq, pool)


print('start running')

env.process(setup(env,ls,1000))
env.run(until=200000)



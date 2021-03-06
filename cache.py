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

class MyEnv(object):
    def __init__(self):
        self.sim = simpy.Environment()
        self.idpool = Pool()

    def process(self, arg):
        return self.env.process(arg)


    def draw(self):
        return self.idpool.draw()

class Dep(object):
    def __init__(self, parent, child):
        self.parent = parent
        self.child = [child]

    def addchild(self, child):
        self.child.append(child)

    def __str__(self):
        buf = "%s -> " % self.parent
        for child in self.child:
            buf += "%s" % child
        return buf


class MSQ(object):
    def __init__(self, env, num_units):
        self.env = env
        self.arbiter = simpy.Resource(env, num_units)
        self.freelist = list(range(0,num_units))  #0..num_units-1
        self.busylist = []

    def Alloc(self):
        assert(not self.freelist)
        unit = self.freelist.pop()
        self.busylist.append(unit)
        return unit

    def Release(self):
        assert(not self.busylist)
        unit = self.busylist.pop()
        self.freelist.append(unit)
        return unit



    def Access(self, unit):
        id = self.env.draw()
        hitL2 = random.uniform(0, 1) < 0.75
        execstr = "MSQ_L2#%d" % (id)
        lat = random.randint(8, 12)
        yield self.env.sim.timeout(lat)
        execstr += "[%d]." % (lat)
        return (0, execstr)



class LoadStore(object):
    def __init__(self, env, msq):
        self.env = env
        self.sim = env.sim
        self.action = self.sim.process(self.run())
        self.msq = msq
        self.msq_arb = simpy.Resource(env, 4)

        #self.run()

    def run(self):
        while True:
            print('@{0:5d} : '.format(self.sim.now), end='')
            duration = 5
            id = self.env.draw()
            execstr = "ldr#%d" % id
            lat = 1
            execstr += "[%d]." % lat
            data_arrival = self.sim.process(self.accessL1(id))
            code, L1_execstr = yield data_arrival
            execstr += L1_execstr
            print("%s" % execstr)



    def accessL1(self, id):
        prob = random.uniform(0,1)
        hitL1 = prob < 0.5
        id = self.env.draw()
        execstr = "L1#%d" % id

        if hitL1:
            lat = random.randint(2,3)  # L1 latency
            execstr += "[%d]." % lat
            yield self.sim.timeout(lat)
            return (0, execstr)
        else: # miss L1
            lat = 2
            execstr += "[%d]." % lat
            # request MSQ
#            miss = self.msq.Request()
#            yield self.sim.process(miss)
            #print('%d MSQ arbiter grant %d' % (self.env.now, alloc))
            yield self.msq_arb.request()


            L2 = self.sim.process(self.msq.Access(0))
            code, L2_execstr = yield L2
                #code, L2_execstr = yield L2
                #L2 = self.sim.process(self.accessL2())
                #code, L2_execstr = yield L2
            execstr += "%s." % L2_execstr
            return (code, execstr)

    def accessL2(self):
        id = self.env.draw()
        hitL2 = random.uniform(0,1) < 0.75
        execstr = "L2#%d" % id
        if hitL2:
            lat = random.randint(8,12)
            yield self.sim.timeout(lat)
            execstr += "[%d]." % lat
            return (0, execstr)
        else: # miss L2
            lat = random.randint(15,30) # memory latency
            yield self.sim.timeout(lat)
            execstr += "[%d]." % lat
            return (1, execstr)





env = MyEnv()
mem = Memory(256,1024)
mem.linearize()
msq = MSQ(env.sim,4)

print("mem has data %s" % mem.data)
mem.write(512,89)

ls = LoadStore(env, msq)
print('start running')
env.sim.run(until=55)



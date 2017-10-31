import simpy
import random

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

class LoadStore(object):
    def __init__(self, env):
        self.env = env
        self.sim = env.sim
        self.action = self.sim.process(self.run())
        #self.run()

    def run(self):
        while True:
            print('Load request at %d' % self.sim.now)
            duration = 5
            id = self.env.draw()

            data_arrival = self.sim.process(self.accessL1())
            code, child = yield data_arrival
            print('Dep %s' % Dep(id, child))

            if (code  == 0):
                print('L1 hit at %d' %  self.sim.now)
            else:
                print('L1 miss %d' % self.sim.now)


    def accessL1(self):
        prob = random.uniform(0,1)
        hitL1 = prob < 0.5
        id = self.env.draw()

        if hitL1:
            L1lat = random.randint(2,3)  # L1 latency
            yield self.sim.timeout(L1lat)
            return (0, Dep(id,-1))
        else: # miss L1
            L2 = self.sim.process(self.accessL2())
            code, child = yield L2
            return (code, Dep(id, child))

    def accessL2(self):
        id = self.env.draw()
        hitL2 = random.uniform(0,1) < 0.75

        if hitL2:
            L2lat = random.randint(8,12)
            yield self.sim.timeout(L2lat)
            return (0, Dep(id, -1))
        else: # miss L2
            Memorylat = random.randint(15,30)
            yield self.sim.timeout(Memorylat)
            return (1, Dep(id, -1))



def main():

    env = MyEnv()

    ls = LoadStore(env)
    print('start running')
    env.sim.run(until=55)


if __name__ == "__main__": main()
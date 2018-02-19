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

    def check(self, addr):
        assert addr>=self.start and addr<=self.end

    def read(self, addr):
        self.check(addr)
        return self.data[addr-self.start]

    def write(self, addr, data):
        self.check(addr)
        self.data[addr-self.start] = data
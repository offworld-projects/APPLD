import cma
import numpy as np
import os.path
import time
import sys

n_samples = 12
dim = 8
n_iters = dim * 100

LOWER = np.array([0.2, 0.7,  3,  3, 0, 0, 0,   0])
UPPER = np.array([2.0, 2.2, 20, 60, 1, 1, 1, 0.5])
DEFAULT = np.array([0.5, 1.57, 6, 20, 0.1, 0.75, 1, 0.3]) 


ENV = sys.argv[1]

DOCKER_NAME = {
	"all"     : "jackal-evaluation-ahg-all",
	"open"    : "jackal-evaluation-ahg-open",
	"curve"   : "jackal-evaluation-ahg-curve",
	"obstacle": "jackal-evaluation-ahg-obstacle",
	"gap"     : "jackal-evaluation-ahg-gap",
}

SLEEP_TIME = {
	"all"     : 80,
	"open"    : 15, 
	"curve"   : 20,
	"obstacle": 18,
	"gap"     : 30,
}

c1 = 12.1
c2 = 9
c3 = 24
c4 = 7.28

def transform(th):
	return (th / 10) * (UPPER-LOWER) + LOWER

def execute(i, th):
	template = "nohup docker run --cpuset-cpus={} --rm {} /home/xuesu/jackal_ws/evaluation/evaluate_all.sh -v {} -w {} -s 2.0 -x {} -t {} -o {} -p {} -g {} -i {} -l 100 > ./results/sample{}.txt 2>&1 &"
	th = transform(th)
	os.system(template.format(i, DOCKER_NAME[ENV], th[0], th[1], int(th[2]), int(th[3]), th[4], th[5], th[6], th[7], i))

def calc_loss(sample_id):
	with open("./results/sample%d.txt" % sample_id, 'r') as f:
		try:
			lines = f.readlines()[-8:]
			v1, w1 = [float(a) for a in lines[0].split()[:2]]
			v2, w2 = [float(a) for a in lines[2].split()[:2]]
			v3, w3 = [float(a) for a in lines[4].split()[:2]]
			v4, w4 = [float(a) for a in lines[6].split()[:2]]
			#print(sample_id, v1, v2, v3, v4)
			return ((v1+w1)*c1 + (v2+w2)*c2 + (v3+w3)*c3 + (v4+w4)*c4)
		except:
			return 1000

def evaluate(thetas):
	err = [0] * 12
	P = 12
	for j in range(P):
		execute(j, thetas[j])

	time.sleep(SLEEP_TIME[ENV])

	for j in range(P):
		err[j] = calc_loss(j)
	return err

def CMA():
	opt = cma.CMAOptions()
	opt['tolfun'] = 1e-11
	opt['popsize'] = n_samples
	opt['maxiter'] = n_iters
	opt['bounds'] = [0, 10]
	mu = np.ones((dim)) * 5
	es = cma.CMAEvolutionStrategy(mu, 2., opt)

	stats = {
		'loss': [],
		'theta': [],
		'mintheta': [],
	}

	best_solution = None
	best_loss = np.inf
	t0 = time.time()

	for i in range(n_iters):
		solutions = es.ask()
		loss = evaluate(solutions)
		loss = np.array(loss)
		idx = np.argmin(loss)
		es.tell(solutions, loss)
		curr_best = np.array(solutions).mean(0)
		curr_min = np.array(solutions)[idx]
		stats['theta'].append(curr_best)
		stats['loss'].append(loss.mean())
		stats['mintheta'].append(curr_min)
		print("[INFO] iter %2d | time %10.4f | avg loss %10.4f | min loss %10.4f" % (
			i,
			time.time() - t0,
			loss.mean(), loss.min()))
		V = transform(curr_best)
		print(V)
		M = transform(curr_min)
		print(M)
		if (i+1) % 5 == 0:
			with open("./stats/{}.npy".format(ENV), 'w') as f:
				np.save(f, stats)

def CEM():
	mu = np.ones((dim)) *5
	std = np.ones((dim))
	extra_std = 1
	extra_decay_time = n_iters // 2
	n_elites = 3

	for i in range(200):
		extra_cov = max(1.0 - i / extra_decay_time, 0) * extra_std**2 + 1e-2
		thetas = np.random.multivariate_normal(
			mean=mu,
			cov=np.diag(np.array(std**2) + extra_cov),
			size=n_samples)

		thetas = thetas.clip(0, 10)
		fx = evaluate(thetas)
		fx = np.array(fx)
		elite_inds = fx.argsort()[:n_elites]
		elite_thetas = thetas[elite_inds]

		mu = elite_thetas.mean(axis=0)
		std = elite_thetas.std(axis=0)
		V = transform(mu)
		print("[INFO] iter %2d | mean loss %10.4f | min loss %10.4f |" % (
			i,
			fx.mean(),
			fx[elite_inds[0]]))
		print(V)

if __name__ == "__main__":
	print("[INFO] testing docker environment ", ENV)
	CMA()
	#for i in range(12):
	#	print(calc_loss(i))

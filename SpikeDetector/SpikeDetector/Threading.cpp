#pragma once

#include <functional>
#include <thread>
#include <vector>
#include <algorithm>

using namespace std;


const int parallelism = std::thread::hardware_concurrency();

void threadedLoop(int data_size, std::function<void(int)> runner, int min_chunk = 200) {

	const int thread_count = min(data_size / min_chunk, parallelism);

	if (thread_count <= 1) {
		for (int j = 0; j < thread_count; j++)
		{
			runner(j);
		}
	}

	const int grainsize = data_size / thread_count;

	std::thread *threads=new thread[thread_count];

	int trail = 0;
	for (int i = 0; i < thread_count; i++)
	{
		int start = trail;
		int end = i + 1 == thread_count ? data_size : trail + grainsize;
		trail = end;


		threads[i]=thread([runner, start, end]()->void {
			for (int j = start; j < end; j++)
			{
				runner(j);
			}
			});
	}

	for (int i = 0; i < thread_count; i++)
	{
		threads[i].join();
	}

	delete[] threads;
}
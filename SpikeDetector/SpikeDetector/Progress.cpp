#pragma once

#include <chrono>
#include <mutex>
#include <string>
#include <functional>
#include <strstream>
#include <iomanip>
#include <sstream>

using namespace std;

class Progress {

private:
	float last_p;
	int total;
	int count = 0;
	chrono::milliseconds last_tim;
	chrono::milliseconds tim_start = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());
	mutex sync;
	std::function<void(string)> log;
	bool mode;
public:
	void increment() {
		sync.lock();
		count++;
		std::chrono::milliseconds ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());

		float precent_f = (count / (float)total);
		float precent = precent_f * 100;
		if (mode ? (precent - last_p) > 2:(ms - last_tim) > std::chrono::milliseconds(1000)) {
			last_tim = ms;
			last_p = precent;

			if (count > 1) {
				auto spent_time = ms - tim_start;
				auto total_time = spent_time / precent_f;

				int ms = (int)(total_time - spent_time).count();

				auto sec = ms / 1000;
				ms -= sec * 1000;
				auto min = sec / 60;
				sec -= min * 60;

				std::stringstream stream;
				stream << std::fixed << std::setprecision(2) << precent;

				log(stream.str() + "% remaining: " + to_string(min) + ":" + to_string(sec) + ":" + to_string(ms));
			}

		}

		sync.unlock();
	}

	Progress(int total, function<void(string)> log, bool mode) {
		this->total = total;
		this->log = log;
		this->mode = mode;
	}
};
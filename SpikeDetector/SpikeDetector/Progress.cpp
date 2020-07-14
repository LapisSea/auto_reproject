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
	mutex sync;
	std::function<void(string)> log;
	bool mode;
public:
	void increment() {
		sync.lock();
		count++;
		std::chrono::milliseconds ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());

		float precent = (count / (float)total) * 100;
		if (mode?(precent - last_p) > 2:(ms - last_tim) > std::chrono::milliseconds(500)) {
			last_tim = ms;
			last_p = precent;

			std::stringstream stream;
			stream << std::fixed << std::setprecision(2) << precent;

			log(stream.str() + "%");
		}

		sync.unlock();
	}

	Progress(int total, function<void(string)> log, bool mode) {
		this->total = total;
		this->log = log;
		this->mode = mode;
	}
};
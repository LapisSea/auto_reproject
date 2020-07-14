
#include "SpikeDetector.h"
#include <string>
#include <iostream>
#include <fstream>
#include <windows.h> 
#include <set>
#include <thread>
#include <unordered_set>
#include <functional>
#include "SafeQueue.cpp"
#include <streambuf>
#include <istream>
#include <streambuf>
#include <string>
#include <strstream>
#include <chrono>
#include <csignal>
#include "Progress.cpp"
#include <filesystem>

using namespace std;

mutex print_lock;

void single_command(string name, string value) {
	print_lock.lock();
	cout << name + " " + value + ";;";
	print_lock.unlock();
}

void log_msg(string message) {
	single_command("log", message);
}

void error(string message) {
	print_lock.lock();
	cout << "error " + message + ";;";
	this_thread::sleep_for(chrono::milliseconds(200));
	print_lock.unlock();
}
void simple_command(string message) {
	print_lock.lock();
	cout << message + " ;";
	print_lock.unlock();
}

void ping_pong() {
	print_lock.lock();
	cout <<  "ping ;";
	int c;
	cin >> c;
	print_lock.unlock();
}

bool report_got;

template <typename T>
T request_command(string message) {
	simple_command(message);
	T val;
	cin >> val;

	if (report_got)log_msg("Got " + message + ": " + to_string(val));
	return val;
}

const int parallelism = thread::hardware_concurrency();

//#define FOR_LOOP(varname, end, code, ...) for(int varname=0;varname<end;varname++)code
#define FOR_LOOP(varname, end, code, ...) threadedLoop(end, [__VA_ARGS__](int varname)->void code);


void threadedLoop(int data_size, std::function<void(int)> runner) {

	int thread_count = min(parallelism, data_size/200);
	if (thread_count <= 1) {
		for (int j = 0; j < thread_count; j++)
		{
			runner(j);
		}
	}

	const int grainsize = data_size / thread_count;

	std::vector<std::thread> threads;

	int trail = 0;
	for (int i = 0; i < thread_count; i++)
	{
		int start = trail;
		int end = i + 1 == thread_count ? data_size : trail + grainsize;
		trail = end;


		threads.push_back(thread([runner, start, end]()->void {
			for (int j = start; j < end; j++)
			{
				runner(j);
			}
			}));
	}

	for (int i = 0; i < threads.size(); i++)
	{
		threads[i].join();
	}
}

int locality;
float standard_derivation_treshold;

int co_size;
float(*co_data)[3];

int edges_size;
int(*edges_data)[2];

struct WeightedIndex {
	int index;
	float weight;

	WeightedIndex(int index, float weight) {
		this->index = index;
		this->weight = weight;
	}
};



void vec3_sub(float dest[3], float left[3], float right[3]) {
	dest[0] = left[0] - right[0];
	dest[1] = left[1] - right[1];
	dest[2] = left[2] - right[2];
}
void vec3_add(float dest[3], float left[3], float right[3]) {
	dest[0] = left[0] + right[0];
	dest[1] = left[1] + right[1];
	dest[2] = left[2] + right[2];
}
float vec3_len(float vec[3]) {
	return sqrtf(vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2]);
}


vector<int>* compute_vertex_to_edge_relations() {

	vector<int>* vertex_to_edge = new vector<int>[co_size];

	for (int i = 0; i < edges_size; i++)
	{
		auto edge = edges_data[i];
		vertex_to_edge[edge[0]].push_back(i);
		vertex_to_edge[edge[1]].push_back(i);
	}

	return vertex_to_edge;
}

float* compute_edge_lengths() {

	float* edge_lengths = new float[edges_size];

	FOR_LOOP(i, edges_size, {
		auto edge = edges_data[i];
		auto co1 = co_data[edge[0]];
		auto co2 = co_data[edge[1]];

		float length_vec[3];
		vec3_sub(length_vec, co1, co2);

		edge_lengths[i] = vec3_len(length_vec);

		},
		edge_lengths);


	return edge_lengths;
}

float* compute_vertex_avarage_lengths(vector<int>* vertex_to_edge) {

	float* edge_lengths = compute_edge_lengths();

	float* lengths = new float[co_size];

	FOR_LOOP(i, co_size, {
		vector<int> index = vertex_to_edge[i];
		float sum = 0;
		for each (auto id in index)
		{
			sum += edge_lengths[id];
		}
		lengths[i] = sum;

		},
		vertex_to_edge, lengths, edge_lengths);

	delete[] edge_lengths;

	return lengths;
}

vector<int>* compute_local_index(int vertex_index, vector<int>* vertex_to_edge) {
	unordered_set<int> local_index;
	unordered_set<int> edge_index;

	local_index.insert(vertex_index);

	for (int _i = 0; _i < locality; _i++) {
		vector<int> new_index;
		for each (int existing_vt in local_index)
		{
			for each (int edge_id in vertex_to_edge[existing_vt])
			{
				if (edge_index.count(edge_id))continue;
				edge_index.insert(edge_id);

				int* edge = edges_data[edge_id];

				if (edge[0] != existing_vt) {
					new_index.push_back(edge[0]);
				}
				if (edge[1] != existing_vt) {
					new_index.push_back(edge[1]);
				}
			}

		}

		for each (int new_id in new_index) {
			local_index.insert(new_id);
		}
		new_index.clear();
	}

	vector<int>* index(new vector<int>);
	index->reserve(local_index.size());
	index->insert(index->end(), local_index.begin(), local_index.end());

	return index;
}

double calculateSD(float data[], int count, double mean)
{
	double standardDeviation = 0.0;

	for (int i = 0; i < count; ++i) {
		standardDeviation += pow(data[i] - mean, 2);
	}
	return sqrt(standardDeviation / count);
}

void push_dataset_filtered_index(float data[], int data_size, std::function<int(int)> index_unmapper, std::function<void(WeightedIndex)> consumer) {
	double sum = 0;
	for (int i = 0; i < data_size; i++) {
		sum += data[i];
	}
	double mean = sum / data_size;

	double sd = calculateSD(data, data_size, mean);
	if (sd < 0.000001) {
		return;
	}

	for (int i = 0; i < data_size; i++) {
		float val = data[i];
		double zscore = (data[i] - mean) / sd;
		if (zscore > standard_derivation_treshold) {
			int global_index = index_unmapper(i);
			consumer(WeightedIndex(global_index, val));
		}
	}
}

void process() {

	log_msg("Computing vertex to edge relations");
	ping_pong();
	vector<int>* vertex_to_edge = compute_vertex_to_edge_relations();

	log_msg("Computing avarage edge lengths");
	ping_pong();
	float* global_dataset = compute_vertex_avarage_lengths(vertex_to_edge);

	log_msg("Computing standard derivation");
	ping_pong();

	vector<WeightedIndex>* result_index(new vector<WeightedIndex>);

	Progress* progress=new Progress(co_size, [](string msg)->void {
		log_msg(msg);
		ping_pong();
		}, false);

	if (locality == 0) {
		push_dataset_filtered_index(
			global_dataset,
			co_size,
			[](int local_i)->int {return local_i; },
			[result_index, progress](WeightedIndex i)->void {
				result_index->push_back(i);
			});
	}
	else {
		FOR_LOOP(vertex_index, co_size, {
			progress->increment();

			auto local_index = compute_local_index(vertex_index, vertex_to_edge);
			auto index_size = local_index->size();

			float* local_dataset = new float[index_size];
			for (int i = 0; i < index_size; i++) {
				int index = (*local_index)[i];
				local_dataset[i] = global_dataset[index];
			}


			push_dataset_filtered_index(
				local_dataset,
				index_size,
				[local_index](int local_i)->int {
					return (*local_index)[local_i];
				},
				[result_index, vertex_index](WeightedIndex entry)->void {
					if (entry.index == vertex_index) {
						result_index->push_back(entry);
					}
				});

			delete[] local_dataset;
			delete local_index;

			},
			vertex_to_edge, global_dataset, result_index, progress);

	}

	delete progress;
	delete[] vertex_to_edge;
	delete[] global_dataset;
	delete[] co_data;
	delete[] edges_data;

	auto final_size = result_index->size();

	float max = 0;
	for (int i = 0; i < final_size; i++)
	{
		float weight = (*result_index)[i].weight;
		if (weight > max)max = weight;
	}

	single_command("feed-results", to_string(final_size));

	for (int i = 0; i < final_size; i++)
	{
		auto entry = (*result_index)[i];
		cout << entry.index << ";";
		cout << entry.weight / max << ";";
	}
}


byte char2int(char input)
{
	if (input >= '0' && input <= '9')
		return input - '0';
	if (input >= 'A' && input <= 'F')
		return input - 'A' + 10;
	if (input >= 'a' && input <= 'f')
		return input - 'a' + 10;

	throw "Invalid hex code " + to_string(input);
}

byte read_2_char_hex(istream& is) {
	char c1;
	char c2;
	is >> c1;
	if (c1 == '\n') {
		is >> c1;
	}
	is >> c2;

	return char2int(c1) * 16 + char2int(c2);
}

std::chrono::milliseconds ms() {
	return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());
}

string size_table[5] = {"B","KB","MB","GB","TB"};

string bytes_readable(float byte_count) {
	int index=0;
	while (byte_count >1024)
	{
		byte_count /= 1024;
		index++;
	}

	std::stringstream stream;
	stream << std::fixed << std::setprecision(2) << byte_count;
	return stream.str() + size_table[index];
}

template <typename T, int dimmensions>
thread download_2d_array(T(*dest)[dimmensions], const int instance_count, string name) {
	auto t1 = ms();

	string str = typeid(int).name();
	single_command(name, str + ";dim=" + to_string(dimmensions));

	int byte_size = instance_count * dimmensions * sizeof(T);

	log_msg("downloading " + to_string(instance_count) + " " + name + " (" + bytes_readable(((float)byte_size)*2) + ")");

	int name_siz;
	cin >> name_siz;

	std::stringstream stream;
	for (int i = 0; i < name_siz; i++)
	{
		char c;
		cin >> c;
		stream << c;
	}
	string file_name = stream.str();
	ifstream filein;
	filein.open(file_name);


	byte* data = new byte[byte_size];


	for (int i=0; i < byte_size; i++)
	{
		data[i] =read_2_char_hex(filein);
	}
	filein.close();

	float passed = (ms() - t1).count()/1000.0;
	
	log_msg(name+" transfer rate " + bytes_readable(byte_size*2/ passed) +"/s");

	return thread([byte_size, data, instance_count, dest, name]()->void {

		int insntace_size = dimmensions * sizeof(T);

		for (int i = 0; i < instance_count; i++) {
			int lower_offset = insntace_size * i;
			std::memcpy(dest[i], data + lower_offset, insntace_size);
		}

		delete[] data;
		log_msg("created " + name);
		});


}

thread download_cords() {
	co_size = request_command<int>("mesh.cordinates.size");
	co_data = new float[co_size][3];
	return download_2d_array<float, 3>(co_data, co_size, "mesh.cordinates");
}

thread download_edges() {
	edges_size = request_command<int>("mesh.edge_index.size");
	edges_data = new int[edges_size][2];
	return download_2d_array<int, 2>(edges_data, edges_size, "mesh.edge_index");
}


int main()
{
	try {
		std::locale::global(std::locale("en_US.UTF-8"));

		report_got = request_command<int>("report_got");

		auto th1 = download_edges();
		auto th2 = download_cords();

		standard_derivation_treshold = request_command<float>("standard_derivation_treshold");
		locality = request_command<int>("locality");

		simple_command("rest");
		ping_pong();

		th1.join();
		th2.join();

		process();

		simple_command("kill");
	}
	catch (const std::exception& e) {
		error(e.what());
	}
	return 0;
}
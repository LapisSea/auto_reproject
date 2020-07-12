
#include "SpikeDetector.h"
#include <string>
#include <iostream>
#include <fstream>
#include <windows.h> 
#include <set>
#include <thread>
#include <unordered_set>
#include <functional>

using namespace std;

const int parallelism = thread::hardware_concurrency();

int locality;
float standard_derivation_treshold;

int co_size;
float(*co_data)[3];

int edges_size;
int(*edges_data)[2];

struct WeightedIndex {
	int index;
	float weight;
};

void single_command(string name, string value) {
	cout << name << " " << value << ";;";
}

void log(string message) {
	single_command("log", message);
}

void error(string message) {
	cout << "error " << message << ";;";
}
void simple_command(string message) {
	cout << message << " ;";
}


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
	float length_vec[3];

	float* edge_lengths = new float[edges_size];

	for (int i = 0; i < edges_size; i++)
	{
		auto edge = edges_data[i];
		auto co1 = co_data[edge[0]];
		auto co2 = co_data[edge[1]];

		vec3_sub(length_vec, co1, co2);

		edge_lengths[i] = vec3_len(length_vec);

	}

	return edge_lengths;
}

float* compute_vertex_avarage_lengths(vector<int>* vertex_to_edge) {

	float* edge_lengths = compute_edge_lengths();

	float* lengths = new float[co_size];

	for (int i = 0; i < co_size; i++) {
		vector<int> index = vertex_to_edge[i];
		float sum = 0;
		for each (auto id in index)
		{
			sum += edge_lengths[id];
		}
		lengths[i] = sum;

	}
	delete[] edge_lengths;

	return lengths;
}

vector<int>* compute_local_index(int vertex_index, vector<int>* vertex_to_edge) {
	unordered_set<int> local_index;
	unordered_set<int> edge_index;

	local_index.insert(vertex_index);

	vector<int> new_index;
	for (int _i = 0; _i < locality; _i++) {

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

float calculateSD(float data[])
{
	float sum = 0.0, mean, standardDeviation = 0.0;

	int i;

	for (i = 0; i < 10; ++i) {
		sum += data[i];
	}

	mean = sum / 10;

	for (i = 0; i < 10; ++i)
		standardDeviation += pow(data[i] - mean, 2);

	return sqrt(standardDeviation / 10);
}

void push_dataset_filtered_index(float data[], int data_size, std::function<int(int)> index_unmapper, std::function<void(int)> consumer) {
	float sd = calculateSD(data);
	if (sd < 0.000001) {
		return;
	}

	double sum = 0;
	for (int i = 0; i < data_size; i++) {
		sum += data[i];
	}
	double mean = sum / data_size;

	for (int i = 0; i < data_size; i++) {
		double zscore = (data[i] - mean) / sd;
		if (zscore > standard_derivation_treshold) {
			consumer(index_unmapper(i));
		}
	}
}

void process() {

	log("Computing vertex to edge relations");
	vector<int>* vertex_to_edge = compute_vertex_to_edge_relations();

	log("Computing avarage edge lengths");
	float* global_dataset = compute_vertex_avarage_lengths(vertex_to_edge);

	log("Computing standard derivation");

	vector<int>* result_index(new vector<int>);

	if (locality == 0) {
		push_dataset_filtered_index(
			global_dataset,
			co_size,
			[](int i)->int {return i; },
			[result_index](int i)->void {
				result_index->push_back(i);
			});
	}
	else {
		for (int vertex_index = 0; vertex_index < co_size; vertex_index++) {
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
				[local_index](int i)->int {
					return (*local_index)[i];
				},
				[result_index, vertex_index](int i)->void {
					if (i == vertex_index) {
						result_index->push_back(i);
					}
				});

		}
	}

	delete[] vertex_to_edge;

	int final_size = result_index->size();

	float* relevant_dataset = new float[final_size];
	for (int i = 0; i < final_size; i++)
	{
		relevant_dataset[i] = global_dataset[(*result_index)[i]];
	}

	delete[] global_dataset;

	float max = 0;
	for (int i = 0; i < final_size; i++)
	{
		float weight = relevant_dataset[i];
		if (weight > max)max = weight;
	}

	single_command("feed-results", to_string(final_size));

	for (int i = 0; i < final_size; i++)
	{
		cout << (*result_index)[i] << ";";
		cout << relevant_dataset[i] / max << ";";
	}
}

void read_floats_human(float* dest, int count) {
	for (int i = 0; i < count; i++)
	{
		std::cin >> dest[i];
	}
}

void read_ints_human(int* dest, int count) {
	for (int i = 0; i < count; i++)
	{
		std::cin >> dest[i];
	}
}

char bb[4 * 3];

void read_floats_binary(float* dest, int count) {
	std::cin.read(bb, sizeof(float) * 3);
	std::memcpy(&dest, bb, sizeof(float) * 3);
}

void read_ints_binary(int* dest, int count) {
	std::cin.read(bb, sizeof(int) * 2);
	std::memcpy(&dest, bb, sizeof(int) * 2);
}

int main()
{
	bool human_mode;
	simple_command("human_mode");
	std::cin >> human_mode;

	string human = "human;";
	string robot = "binary;LE;bytes=4;";
	string encoding = human_mode ? human : robot;


	bool report_got;
	simple_command("report_got");
	std::cin >> report_got;

	single_command("mesh.cordinates", encoding + "float;dim=3");
	std::cin >> co_size;

	co_data = new float[co_size][3];


	for (int i = 0; i < co_size; i++)
	{
		if (human_mode)read_floats_human(co_data[i], 3);
		else read_floats_binary(co_data[i], 3);
	}

	if (report_got)log("got " + to_string(co_size) + " vertices");

	single_command("mesh.edge_index", encoding + "int;dim=2");
	std::cin >> edges_size;

	edges_data = new int[edges_size][2];

	for (int i = 0; i < edges_size; i++)
	{
		if (human_mode)read_ints_human(edges_data[i], 2);
		else read_ints_binary(edges_data[i], 2);
	}
	if (report_got)log("got " + to_string(edges_size) + " edges");

	simple_command("locality");
	std::cin >> locality;
	if (report_got)log("got locality: " + to_string(locality));


	simple_command("standard_derivation_treshold");
	std::cin >> standard_derivation_treshold;
	if (report_got)log("got standard_derivation_treshold: " + to_string(standard_derivation_treshold));

	simple_command("rest");
	process();

	std::cin.ignore();
	return 0;
}
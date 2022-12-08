class Solution {
public:
vector<vector<int>> result;
vector<vector<int>> combine(int n, int k) {
    vector<int> record;
    combinationsHelper(record, 1, n, k);
    return result;
}

void combinationsHelper(vector<int> &record, 
                int start, int n, int k) {
    if (record.size() == k)
    {
        result.push_back(record);
        return;
    }

    for (int i=start; i<=n; i++)
    {
        record.push_back(i);
        //cout<<i<<endl;
        combinationsHelper(record, i+1, n, k);//1 to 2, 2 to 3 and first 2 pop 
        //cout<<record[0]<<" "<<record[1]<<endl;
        //cout<<"pop"<<endl;
        record.pop_back();//移最後那一個值而已
    }
}
};

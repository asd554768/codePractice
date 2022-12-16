class Solution {
public:
    vector<int> findAnagrams(string s, string p) {
        vector <int> result;
        if(s.size()<p.size()) return result;
        unordered_map<char,int> mpS;
        unordered_map<char,int> mpP;
        int index=0;
        int left=0;
        for(;index<p.size();index++){
            mpS[s[index]]++;
            mpP[p[index]]++;
        }
        if(mpS==mpP) result.push_back(left);
        for(;index<s.size();index++){
            
            mpS[s[left]]--;
            if(mpS[s[left]]==0) mpS.erase(s[left]);
            left++;
            mpS[s[index]]++;
            if(mpS==mpP) result.push_back(left);//關鍵，可以直接讓vector和hashtable進行布林判斷
                
             
        }
        return result;
    }
};
class Solution {
public:
    bool backspaceCompare(string s, string t) {
        stack<char> stS;
        stack<char> stT;
        //loopLen=max(s.size(),t.size());
        //minLen=min(s.size(),t.size());
        for(int i=0;i<s.size();i++){
            if(s[i]=='#' ){
                if(!stS.empty()){
                    stS.pop();
                }
                
            }else{
                stS.push(s[i]);
            }
        }
        for(int i=0;i<t.size();i++){
            if(t[i]=='#'){
                
                if(!stT.empty()){
                    //cout<<stT.top()<<endl;
                    stT.pop();
                }
                
            }else{
                stT.push(t[i]);
            }
        }    

        return stS==stT;    
    }
};
/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    ListNode* mergeTwoLists(ListNode* list1, ListNode* list2) {
        int val=0;
        if(!list1){
            return list2;
        }else if(!list2){
            return list1;
        }
        if(list1->val>list2->val){
            val=list2->val;
            list2=list2->next;
        }else{
            val=list1->val;
            list1=list1->next;
        }
        ListNode *link=new ListNode(val);
         ListNode *result=link;
        while(list1 && list2){
            if(list1->val>list2->val){
                val=list2->val;
                list2=list2->next;
            }else{
                val=list1->val;
                list1=list1->next;
            }
            ListNode *temp=new ListNode(val);
            link->next=temp;
            link=link->next;            
        }
        if(!list1 && list2){
            link->next=list2;
        }else if(!list2 && list1){
            link->next=list1;
        }        
        return result;
    }
};
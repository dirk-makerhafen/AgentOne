// API functions for agents/consumers/instance_views.py
const instanceViewApi = {
    getByWorkingDirectory: function() {
        sendRequest('instance_view_get_by_dir');
    },
    getByFork: function() {
        sendRequest('instance_view_get_by_fork');
    },
    // Add a way to get the default flat list view as well
    getByAgent: function() {
        sendRequest('agent_list'); // This existing endpoint already sends the flat list
    }
};

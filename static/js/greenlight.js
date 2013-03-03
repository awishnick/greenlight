angular.module('greenlightServices', ['ngResource'])
    .factory('Project', function($resource) {
        return $resource('/api/projects/:projectId', {}, {
            query: {
                method: 'GET',
                isArray: false
            }
        });
    });

angular.module('greenlight', ['greenlightServices'])
    .config(['$routeProvider', function($routeProvider) {
        $routeProvider
            .when('/projects', {
                templateUrl: 'templates/project-list.html',
                controller: ProjectListCtrl
            })
            .when('/projects/:projectId', {
                templateUrl: 'templates/project-detail.html',
                controller: ProjectDetailCtrl
            })
            .otherwise({redirectTo: '/projects'});
    }])
    .directive('spinner', function() {
        return {
            restrict: 'E',
            replace: true,
            transclude: true,
            template: '<div ng-transclude style="margin: 10px 10px 10px 10px;"></div>',
            link: function(scope, element, attrs) {
                var opts = {

                }
                var opts = {
                    lines: 13, // The number of lines to draw
                    length: 4, // The length of each line
                    width: 2, // The line thickness
                    radius: 5, // The radius of the inner circle
                    corners: 1, // Corner roundness (0..1)
                    rotate: 0, // The rotation offset
                    color: '#000', // #rgb or #rrggbb
                    speed: 1, // Rounds per second
                    trail: 60, // Afterglow percentage
                    shadow: false, // Whether to render a shadow
                    hwaccel: false, // Whether to use hardware acceleration
                    //className: 'spinner', // The CSS class to assign to the spinner
                    zIndex: 2e9, // The z-index (defaults to 2000000000)
                    top: '100', // Top position relative to parent in px
                    left: '100' // Left position relative to parent in px
                };
                var spinner = new Spinner(opts).spin();
                element.append(spinner.el);
            }
        }
    });

function ProjectListCtrl($scope, $timeout, Project) {
    $scope.projects = Project.query();

    function updateTimer() {
        $timeout(function() {
            var update = Project.query(function() {
                do_update = false;
                for (i in update) {
                    if (!update.hasOwnProperty(i)) {
                        continue;
                    }
                    if (!(i in $scope.projects)) {
                        do_update = true;
                        break;
                    }

                    project = update[i];
                    old_project = $scope.projects[i];

                    if (project.up_to_date != old_project.up_to_date) {
                        do_update = true;
                        break;
                    }
                    if (project.returncode != old_project.returncode) {
                        do_update = true;
                        break;
                    }
                    if (project.mtime != old_project.mtime) {
                        do_update = true;
                        break;
                    }
                }

                if (do_update) {
                    $scope.projects = update;
                }
            });
            updateTimer();
        }, 1000);
    };

    updateTimer();
}

function ProjectDetailCtrl($scope, $routeParams, Project) {
    $scope.project = Project.get({projectId: $routeParams.projectId});
}

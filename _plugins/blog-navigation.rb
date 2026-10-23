# Normalize imported category paths without changing the post metadata or URLs.
module BlogNavigation
  def self.tree(posts)
    root = { 'children' => {}, 'posts' => [], 'count' => 0 }
    posts.each do |post|
      path = post.data.fetch('categories', []).first(3).map(&:strip)
      path.pop if path.last == post.data.fetch('title', '').strip
      path = ['미분류'] if path.empty?
      node = root
      path.each do |name|
        node = (node['children'][name] ||= { 'children' => {}, 'posts' => [], 'count' => 0 })
        node['count'] += 1
      end
      node['posts'] << post
    end
    root
  end
end

Jekyll::Hooks.register :site, :pre_render do |site|
  site.data['blog_tree'] = BlogNavigation.tree(site.posts.docs.reverse)
end

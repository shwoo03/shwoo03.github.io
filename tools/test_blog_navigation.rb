require 'jekyll'
require 'nokogiri'
require_relative '../_plugins/blog-navigation'

def check(value, message)
  raise message unless value
end

fixture = Struct.new(:data).new( { 'title' => '글', 'categories' => ['A', 'B', 'C'] })
tree = BlogNavigation.tree([fixture])
check(tree.dig('children', 'A', 'children', 'B', 'children', 'C', 'posts') == [fixture], 'Three category levels must remain expandable')
fixture.data['categories'] = ['A', 'B', '글']
tree = BlogNavigation.tree([fixture])
check(tree.dig('children', 'A', 'children', 'B', 'posts') == [fixture], 'Repeated title must be a leaf, not another folder')
fixture.data['categories'] = []
check(BlogNavigation.tree([fixture]).dig('children', '미분류', 'posts') == [fixture], 'Uncategorized posts must remain reachable')

root = File.expand_path('../_site', __dir__)
home = Nokogiri::HTML(File.read(File.join(root, 'index.html')))
check(home.at_css('#sidebar #sidebar-toggle'), 'Toggle must belong to the sidebar')
check(!home.at_css('.content-header #sidebar-toggle'), 'Content header must not own the toggle')
check(!home.at_css('.prototype-bar'), 'Layout comparison must not appear in the selected design')
Dir.glob(File.join(root, 'posts/*/index.html')).each do |path|
  page = Nokogiri::HTML(File.read(path))
  check(page.at_css('.article-content .notion-page'), "Missing original content: #{path}")
  canonical = page.at_css('link[rel="canonical"]')['href']
  article_url = URI.parse(canonical).path
  listed = page.css('#sidebar .tree-post').find { |link| link['href'] == article_url }
  check(listed ? listed['aria-current'] == 'page' : page.at_css('#sidebar .tree-more'), "Missing current article or full-list link: #{path}")
end
# Render the real recursive include with more posts than the sidebar can display.
site = Jekyll::Site.new(Jekyll.configuration('source' => File.expand_path('..', __dir__), 'quiet' => true))
posts = (1..12).map { |n| { 'title' => "글 #{n}", 'date' => Time.utc(2026, 1, n), 'url' => "/posts/test-#{n}/" } }
leaf = { 'children' => {}, 'posts' => posts, 'count' => posts.size }
large_tree = { 'children' => { 'CTF' => { 'children' => { 'CTF 디스코드 구축' => leaf }, 'posts' => [], 'count' => posts.size } }, 'posts' => [] }
render_tree = lambda do |limit|
  source = "{% include blog-tree.html node=tree path='sidebar' #{limit ? 'limit=10' : ''} %}"
  html = Liquid::Template.parse(source).render!({ 'tree' => large_tree, 'page' => {}, 'site' => { 'baseurl' => '' } }, registers: { site: site })
  Nokogiri::HTML.fragment(html)
end
limited = render_tree.call(true)
check(limited.css('.tree-post').map { |link| link['href'] } == (3..12).to_a.reverse.map { |n| "/posts/test-#{n}/" }, 'Sidebar must show only the newest ten posts')
check(limited.at_css('.tree-more')['href'] == '/categories/ctf-%EB%94%94%EC%8A%A4%EC%BD%94%EB%93%9C-%EA%B5%AC%EC%B6%95/', 'Older posts must link to the actual category')
check(limited.at_css('.tree-more').text.include?('12'), 'Full-list link must preserve total count')
check(render_tree.call(false).css('.tree-post').size == 12, 'Category page must remain unlimited')
leaf['posts'] = posts.first(10)
check(render_tree.call(true).css('.tree-more').empty?, 'Ten posts must not show an unnecessary more link')
puts 'Blog navigation checks passed.'

use loon_lang::interp::Value;
use std::collections::HashMap;

pub struct AdtCache {
    cache: HashMap<String, CacheEntry>,
    max_entries: usize,
    access_seq: u64,
}

struct CacheEntry {
    value: Value,
    last_access: u64,
}

impl AdtCache {
    pub fn new(max_entries: usize) -> Self {
        Self {
            cache: HashMap::new(),
            max_entries: max_entries.max(1),
            access_seq: 0,
        }
    }

    pub fn set(&mut self, node_id: &str, value: Value) {
        self.access_seq += 1;
        self.cache.insert(
            node_id.to_string(),
            CacheEntry {
                value,
                last_access: self.access_seq,
            },
        );
        self.evict_if_needed();
    }

    pub fn get(&mut self, node_id: &str) -> Option<&Value> {
        self.access_seq += 1;
        let seq = self.access_seq;
        self.cache.get_mut(node_id).map(|entry| {
            entry.last_access = seq;
            &entry.value
        })
    }

    #[allow(dead_code)]
    pub fn has(&self, node_id: &str) -> bool {
        self.cache.contains_key(node_id)
    }

    #[allow(dead_code)]
    pub fn invalidate(&mut self, node_id: &str) {
        self.cache.remove(node_id);
    }

    #[allow(dead_code)]
    pub fn clear(&mut self) {
        self.cache.clear();
    }

    #[allow(dead_code)]
    pub fn len(&self) -> usize {
        self.cache.len()
    }

    fn evict_if_needed(&mut self) {
        while self.cache.len() > self.max_entries {
            let lru_key = self
                .cache
                .iter()
                .min_by_key(|(_, e)| e.last_access)
                .map(|(k, _)| k.clone());
            if let Some(key) = lru_key {
                self.cache.remove(&key);
            } else {
                break;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_value(tag: &str) -> Value {
        Value::Adt(tag.to_string(), vec![Value::Int(1)])
    }

    #[test]
    fn test_set_and_get() {
        let mut cache = AdtCache::new(10);
        cache.set("a", make_value("Cube"));
        assert!(cache.has("a"));
        assert_eq!(cache.len(), 1);
        let val = cache.get("a");
        assert!(val.is_some());
    }

    #[test]
    fn test_invalidate() {
        let mut cache = AdtCache::new(10);
        cache.set("a", make_value("Cube"));
        cache.invalidate("a");
        assert!(!cache.has("a"));
        assert_eq!(cache.len(), 0);
    }

    #[test]
    fn test_clear() {
        let mut cache = AdtCache::new(10);
        cache.set("a", make_value("Cube"));
        cache.set("b", make_value("Sphere"));
        cache.clear();
        assert_eq!(cache.len(), 0);
    }

    #[test]
    fn test_lru_eviction() {
        let mut cache = AdtCache::new(2);
        cache.set("a", make_value("Cube"));
        cache.set("b", make_value("Sphere"));
        // Access "a" to make it recently used
        cache.get("a");
        // Add "c" — should evict "b" (least recently used)
        cache.set("c", make_value("Cylinder"));
        assert_eq!(cache.len(), 2);
        assert!(cache.has("a"));
        assert!(!cache.has("b"));
        assert!(cache.has("c"));
    }

    #[test]
    fn test_max_entries_minimum_one() {
        let mut cache = AdtCache::new(0);
        cache.set("a", make_value("Cube"));
        assert_eq!(cache.len(), 1);
        cache.set("b", make_value("Sphere"));
        assert_eq!(cache.len(), 1);
    }
}

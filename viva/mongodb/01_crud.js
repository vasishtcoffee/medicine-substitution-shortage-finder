// Demonstrates CRUD in the actual app collections, not invented collections.
// Run: MONGO_DATABASE=medsub_viva_<suffix> mongosh "mongodb://127.0.0.1:<port>" --file viva/mongodb/01_crud.js
// PowerShell: $env:MONGO_DATABASE='medsub_viva_<suffix>'; mongosh <URI> --file viva/mongodb/01_crud.js
// Prerequisite: init_mongo.py run with that database. Uses validators/indexes from app/mongo.py.
// AFFECTED: exactly one new UUID-named feed_events document. No inventory feed writes.
// Expected: insert/read notes='created', update notes='reviewed', final count=0.
// Cleanup: finally deletes only this script's document; no dropDatabase/dropCollection.
const name = process.env.MONGO_DATABASE || '';
if (!/^medsub_viva_[a-z0-9_]+$/.test(name)) throw new Error('Select a dedicated medsub_viva_<suffix> database');
const viva = db.getSiblingDB(name);
if (!viva.getCollectionNames().includes('feed_events') || !viva.getCollectionNames().includes('inventory_feed')) throw new Error('Run init_mongo.py first');
const id = 'viva:' + UUID().toString();
print('Affects only feed_events document ' + id + ' in ' + name);
try {
  viva.feed_events.insertOne({_id:id,source:'import',occurred_at:new Date(),payload:{viva:true},notes:'created',flags:['viva']});
  if (viva.feed_events.findOne({_id:id}).notes !== 'created') throw new Error('Create/read invariant failed');
  printjson(viva.feed_events.findOne({_id:id}));
  viva.feed_events.updateOne({_id:id},{$set:{notes:'reviewed'}});
  if (viva.feed_events.findOne({_id:id}).notes !== 'reviewed') throw new Error('Update invariant failed');
  printjson(viva.inventory_feed.find({}, {quantity:1,availability:1}).limit(3).toArray());
} finally {
  viva.feed_events.deleteOne({_id:id});
}
if (viva.feed_events.countDocuments({_id:id}) !== 0) throw new Error('Delete invariant failed');
print('CRUD invariants passed; demonstration document removed');
